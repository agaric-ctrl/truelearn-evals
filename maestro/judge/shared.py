"""Framework-agnostic pieces shared by every Tier 3 judge implementation (deepeval, ragas, ...).

Deliberately has zero *conflicting* framework-specific imports - no deepeval, no ragas. DeepEval
and RAGAS conflict on the click dependency and must live in separate venvs (requirements-maestro.txt
vs requirements-maestro-ragas.txt), so anything both judge modules need has to live somewhere
neither of them owns, or importing one judge module would transitively require the other judge's
conflicting dependency to even be installed.

`anthropic` (below) is the one exception, and it's safe: it's the base provider SDK both deepeval's
AnthropicModel and ragas's ChatAnthropic already wrap, it's already a direct or transitive
dependency in *both* venvs (requirements-maestro.txt and requirements-maestro-ragas.txt), and it
carries none of the click-version conflict - it doesn't reintroduce the problem this module exists
to avoid.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

import anthropic

from maestro.generation.payload import ReferencesPayload

EXPERIMENTAL_LABEL = "[EXPERIMENTAL - NOT VALIDATED AGAINST REAL SME AGREEMENT] "

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def build_actual_output(
    explanation_header: str, explanation_footer: str, bottom_line: str | None = None,
) -> str:
    return "\n\n".join(part for part in (explanation_header, explanation_footer, bottom_line) if part)


def build_retrieval_context_from_references(references: ReferencesPayload) -> list[str] | None:
    """None (never []) when no result carries captured text - an empty list would read downstream
    as "valid but zero-length context", not "nothing gradable exists yet". Whether the real
    Maestro payload ever populates ReferenceResult.text is UNCONFIRMED; this returns None until it
    does.

    Caller-facing rule: a None return means the caller MUST Skip the judge call entirely, never
    pass an empty/meaningless retrieval_context into a faithfulness judge - both deepeval's
    FaithfulnessMetric and ragas's Faithfulness metric treat that argument as real evidence to check
    claims against, and a non-empty-but-content-free list would silently produce a meaningless
    score instead of an honest Skip.

    Partial availability (some results have text, some don't) includes only the ones that do,
    rather than nulling out the whole set - a judge can meaningfully grade against partial source
    material; only the fully-empty case has nothing to grade against.

    TODO(once ReferenceResult.text availability is confirmed): a real caller belongs in
    maestro/generation/ - e.g. judge_history_head(payload, topic) would do
    `context = build_retrieval_context_from_references(payload.history[0].references)`, Skip if
    None, otherwise call a judge_faithfulness* function with source=context. Not built now - live
    URL-fetching to backfill missing text is explicitly out of scope, and this helper is not wired
    into any gate, script, or CI job by this change.
    """

    texts = [result.text for result in references.results if result.text]
    return texts or None


def parse_json_response(text: str) -> dict:
    """Claude is asked for raw JSON but sometimes wraps it in a ```json fence anyway - strip one if
    present, then parse. Raises json.JSONDecodeError (not swallowed) on genuinely malformed output:
    a judge that can't be parsed is a real problem to surface, not a case to silently skip."""

    return json.loads(_JSON_FENCE_RE.sub("", text.strip()))


def call_claude_json(
    system_prompt: str,
    user_content: str,
    *,
    model: str = "claude-sonnet-4-6",
    call: Callable[[], Any] | None = None,
) -> tuple[dict, Any]:
    """Makes one Claude call and returns (parsed_json_response, raw_api_response).

    Used by maestro/judge/non_contradiction.py and maestro/judge/source_coverage.py - two
    genuinely new, independently-designed Tier 3 checks that each need a custom structured-output
    prompt neither deepeval nor ragas exposes as a packaged metric (see each module's own docstring
    for why). Sharing this one low-level "call Claude, parse JSON, surface usage" helper is a code-
    reuse decision, not a design merge: the two judges still use entirely different prompts,
    parsing schemas, fixtures, and pass/fail criteria, and are always invoked as two separate calls
    producing two separate CaseResults - this only avoids retyping retry/parsing boilerplate twice.

    `call` is the test-injection point (real callers omit it): when supplied, no `anthropic.Anthropic()`
    client is constructed at all - building one requires ANTHROPIC_API_KEY, and constructing it
    unconditionally would defeat the whole point of injecting a fake response in a test, same
    convention as judge_faithfulness()'s metric_factory and judge_faithfulness_ragas()'s
    scorer_factory. `call` takes no arguments and returns a raw Anthropic Message-shaped response
    (needs a `.content[0].text` and a `.usage` attribute/key - a real `anthropic.types.Message` or a
    fake test double satisfies this).
    """

    if call is None:
        client = anthropic.Anthropic()

        def call():
            return client.messages.create(
                model=model,
                max_tokens=1024,
                temperature=0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )

    from tools.retry import retry_call

    response = retry_call(call, operation_name="maestro.judge.custom_prompt")
    parsed = parse_json_response(response.content[0].text)
    return parsed, response
