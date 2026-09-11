"""Tier 3 judge: non-contradiction. See maestro/judge/__init__.py for the EXPERIMENTAL status this
whole subpackage carries - applies here identically. Validated only against
maestro/judge/fixtures/non_contradiction_cases.json (hand-crafted, NOT real SME judgment).

Per docs/qa-context/TIER3_JUDGES_TASK.md point 1 and docs/qa-context/MAESTRO_QA_FINDINGS.md Section
2: faithfulness (maestro/judge/faithfulness.py) and non-contradiction are DIFFERENT checks. A
generation can be fully traceable to source (every claim it makes is backed by something in the
source) and still contradict part of that same source elsewhere - faithfulness's claim-support
ratio has no way to notice that, because it only ever asks "is this claim supported?", never "does
this claim conflict with a *different* part of the source?". This module is the check for that
second, distinct failure mode.

DESIGN DECISION (documented per the task's explicit instruction, same discipline as the merged-cell
and Roman-numeral fixes elsewhere in this repo): neither deepeval's packaged metrics nor ragas's
packaged metrics expose a contradiction signal. DeepEval's FaithfulnessMetric and ragas's
Faithfulness metric both only ever answer "is every claim supported by the source" - unsupported
is not the same as contradicted (a claim can be simply absent from the source, which is neither
faithful-and-consistent nor a contradiction; only a claim that actively conflicts with something
the source *does* state counts here). Getting a real contradiction signal means asking a model
directly, in a custom structured prompt, rather than reusing either framework's metric plumbing -
that's a deliberate step outside both frameworks, not an oversight. See
maestro/judge/shared.py's call_claude_json() for the (framework-agnostic, not deepeval/ragas)
low-level "call Claude, parse JSON" plumbing this reuses - shared with source_coverage.py for the
same reason two mechanically-different existing judges share build_actual_output(): identical
low-level need, entirely different judging logic and criteria.

NOT a bolt-on to faithfulness.py and NOT merged with source_coverage.py into one "does both"
judge (task points 1 and 4, explicitly): this is its own module, its own prompt, its own fixture,
its own CaseResult, always called on its own. The existing three-judge redundancy (deepeval/ragas/
Promptfoo all independently checking faithfulness) is a different, deliberate property this module
does not touch or replace.
"""

from __future__ import annotations

from typing import Callable

from maestro.judge.shared import EXPERIMENTAL_LABEL, call_claude_json
from tools.eval_result import CaseResult
from tools.provider_usage import usage_from_objects

# PLACEHOLDER threshold, not calibrated against any real content or real SME judgment - same
# caveat as Tier 1's readability check (docs/qa-context/TIER1_CHECKS_TASK.md) and the existing
# faithfulness judges' score thresholds. 0 is the safest default (any detected contradiction
# fails) but is a real, substantive policy choice - a human reviewer might later decide a minor,
# non-clinically-significant contradiction shouldn't fail the check. That severity-weighting isn't
# built; this constant is the one place to change once real calibration data/policy exists.
MAX_ALLOWED_CONTRADICTIONS = 0

_SYSTEM_PROMPT = """You are checking a generated medical explanation for CONTRADICTIONS against its \
cited source material. A contradiction is a statement in the generated text that directly \
conflicts with something the source material actually states - not a statement that is merely \
absent from the source (that is a different, separate concern, not your job here).

Respond with ONLY a JSON object, no other text, in exactly this shape:
{"contradictions": [{"statement": "<exact or near-exact quote from the generated text>", \
"conflicts_with": "<exact or near-exact quote from the source material it conflicts with>"}], \
"reason": "<one sentence explaining your overall verdict>"}

If there are no contradictions, return an empty "contradictions" list."""


def _default_call(source: list[str], topic: str, generated_text: str) -> tuple[dict, object]:
    user_content = (
        f"TOPIC: {topic}\n\n"
        f"SOURCE MATERIAL:\n" + "\n".join(f"- {s}" for s in source) + "\n\n"
        f"GENERATED TEXT:\n{generated_text}"
    )
    return call_claude_json(_SYSTEM_PROMPT, user_content)


def judge_non_contradiction(
    case_id: str,
    source: list[str],
    topic: str,
    generated_text: str,
    *,
    call_fn: Callable[[list[str], str, str], tuple[dict, object]] | None = None,
) -> tuple[CaseResult, dict | None]:
    """Runs the non-contradiction judge on one Maestro explanation. Returns
    (CaseResult, usage_dict_or_None) - same contract as judge_faithfulness()/judge_faithfulness_ragas().

    Score is binary (1.0 = no contradictions found, 0.0 = at least one found), unlike
    faithfulness's continuous supported-claims/total-claims ratio - contradiction-detection has no
    equivalent natural denominator to grade against (there's no fixed "number of possible
    contradictions" the way there's a fixed number of claims to check support for), so a graded
    score would imply a precision this check doesn't have. This is a documented design choice, not
    an oversight.

    CaseResult.claims is left empty, same reasoning as the other two judges: it's shaped for
    claim/supported/evidence, which doesn't fit a contradiction record (statement/conflicts_with)
    without stretching the schema's meaning. The actual contradictions found are described in full
    inside `reason` instead.

    call_fn is the test-injection point, same role as judge_faithfulness()'s metric_factory: when
    supplied, no real Claude call is made and no client is constructed - see
    maestro/judge/shared.py's call_claude_json() docstring.
    """

    call = call_fn or _default_call
    parsed, raw_response = call(source, topic, generated_text)

    contradictions = parsed.get("contradictions", [])
    # score reports the raw finding (any contradiction at all); passed applies the separate,
    # configurable MAX_ALLOWED_CONTRADICTIONS threshold - kept distinct so a future non-zero
    # threshold doesn't make score itself misleadingly claim "fully clean".
    score = 0.0 if contradictions else 1.0
    passed = len(contradictions) <= MAX_ALLOWED_CONTRADICTIONS

    if contradictions:
        detail = "; ".join(
            f'"{c["statement"]}" conflicts with "{c["conflicts_with"]}"' for c in contradictions
        )
    else:
        detail = "No contradictions found."

    result = CaseResult(
        case_id=case_id,
        score=score,
        passed=passed,
        reason=EXPERIMENTAL_LABEL + parsed.get("reason", "") + " " + detail,
    )
    usage = usage_from_objects(raw_response) if raw_response is not None else None
    return result, usage
