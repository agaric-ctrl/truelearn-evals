"""Framework-agnostic pieces shared by every Tier 3 judge implementation (deepeval, ragas, ...).

Deliberately has zero framework-specific imports - no deepeval, no ragas. DeepEval and RAGAS
conflict on the click dependency and must live in separate venvs (requirements-maestro.txt vs
requirements-maestro-ragas.txt), so anything both judge modules need has to live somewhere neither
of them owns, or importing one judge module would transitively require the other judge's
conflicting dependency to even be installed.
"""

from __future__ import annotations

from maestro.generation.payload import ReferencesPayload

EXPERIMENTAL_LABEL = "[EXPERIMENTAL - NOT VALIDATED AGAINST REAL SME AGREEMENT] "


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
