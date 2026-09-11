"""Tier 3 judge: source coverage. See maestro/judge/__init__.py for the EXPERIMENTAL status this
whole subpackage carries - applies here identically. Validated only against
maestro/judge/fixtures/source_coverage_cases.json (hand-crafted, NOT real SME judgment).

Per docs/qa-context/TIER3_JUDGES_TASK.md point 2: this is the literal mirror image of
faithfulness.py, not a rename of the existing "completeness"/required-fields check
(maestro/checks/required_fields_present.py, which is deterministic and checks whether specific
GeneratedQuestion *fields* are non-empty - a structural check, unrelated to this one).
Faithfulness asks "does everything the generated text states map back to the source" (source ->
generated, checking for unsupported additions). This asks the opposite direction: "does everything
in the source that should be stated actually appear in the generated text" (source -> generated,
checking for silent omissions). Same grounding material, opposite direction of the same underlying
comparison - a generation can be perfectly faithful (adds nothing unsupported) while still silently
dropping most of what the source actually said, and faithfulness's claim-support ratio has no way
to notice that, because it only ever decomposes the *generated* text, never the source.

DESIGN DECISION, same discipline as non_contradiction.py's: neither deepeval's nor ragas's packaged
metrics measure this. DeepEval's ContextualRecallMetric and ragas's context_recall both measure
*retriever* recall (whether a separately-supplied expected_output can be attributed to the
retrieved context) - a different question about the retrieval step, not about whether the
*generator* actually used what was retrieved. There is no packaged "did the generator cover the
source" metric in either framework, so this uses the same custom-structured-prompt approach as
non_contradiction.py, via maestro/judge/shared.py's call_claude_json() - shared low-level plumbing,
entirely separate judging logic, criteria, prompt, and fixture from that module. See
non_contradiction.py's own docstring for the fuller "why shared plumbing isn't a design merge"
rationale; it applies identically here.

NOT merged with non_contradiction.py into one "does both" judge (task point 4, explicitly): this is
its own module, its own prompt, its own fixture, its own CaseResult, always called on its own.

SCOPE - EXAM QUESTIONS ONLY. DO NOT RUN THIS AGAINST ARTICLE CONTENT.
====================================================================
This judge applies to exam-question explanations, where the retrieved/cited material genuinely is
the content's source and "did the generation drop something the source said" is a meaningful
question. It is NOT a valid check for Maestro's long-form ARTICLES, and running it on one produces
a confident, low, meaningless score.

Why, per maestro/CLAUDE.md's settled facts and MAESTRO_QA_FINDINGS.md Section 2 (confirmed directly
by the Data Science lead): an article is written mostly from the model's own medical knowledge,
because the question bank doesn't have the depth to serve as source text. The ~25 retrieved
questions CONSTRAIN the writing (terminology, tested associations) rather than SOURCE it. This
judge's core question - "does everything in the source appear in the generated text" - silently
assumes a sourcing relationship articles don't have by design, and would treat every article as
dropping nearly all of its "source". That test fails every article, by design, no matter how good
the article is.

What articles need INSTEAD (NOT BUILT - no owner, no task doc covers it yet):
  - contradiction rate against the grounding questions -> maestro/judge/non_contradiction.py
    already does exactly this, and IS valid for articles.
  - terminology / tested-association alignment with the bank -> genuinely unbuilt. This is the
    real gap for article evaluation; it is not this judge under another name, and it should not be
    approximated by loosening this judge's threshold.

CONCRETE MISUSE PATH THIS NOTE EXISTS TO PREVENT (a real code path today, not hypothetical):
maestro/golden/tier1_validate_articles.py's article_to_generated_question() deliberately maps a
whole article body into GeneratedQuestion.explanation_footer so Tier 1's deterministic checks can
run on it. That conversion makes an article structurally indistinguishable from a question to
anything downstream - including maestro/comparative/run_variant_pair.py's _available_judges(),
which auto-includes this judge for any GeneratedQuestion-shaped variant output. Nothing in the code
will stop you; the caller is responsible for not routing article content here.
"""

from __future__ import annotations

from typing import Callable

from maestro.judge.shared import EXPERIMENTAL_LABEL, call_claude_json
from tools.eval_result import CaseResult
from tools.provider_usage import usage_from_objects

# PLACEHOLDER threshold, not calibrated against any real content or real SME judgment - same
# caveat as faithfulness.py's threshold=0.9 and Tier 1's readability check. 0.8 is illustrative
# (allows some tolerance for source material a human might reasonably judge as background/
# redundant rather than essential to state), not a validated cutoff - replace once real
# calibration data exists.
COVERAGE_THRESHOLD = 0.8

_SYSTEM_PROMPT = """You are checking whether a generated medical explanation OMITS material \
information from its source. First, decompose the source material into distinct, atomic factual \
statements. Then, for each one, determine whether that fact is reflected (stated or clearly, \
unambiguously implied) anywhere in the generated text.

Respond with ONLY a JSON object, no other text, in exactly this shape:
{"source_statements": [{"statement": "<one atomic fact from the source>", "covered": true or \
false}], "reason": "<one sentence explaining your overall verdict>"}

Every distinct fact in the source material must appear as exactly one entry in "source_statements"."""


def _default_call(source: list[str], topic: str, generated_text: str) -> tuple[dict, object]:
    user_content = (
        f"TOPIC: {topic}\n\n"
        f"SOURCE MATERIAL:\n" + "\n".join(f"- {s}" for s in source) + "\n\n"
        f"GENERATED TEXT:\n{generated_text}"
    )
    return call_claude_json(_SYSTEM_PROMPT, user_content)


def judge_source_coverage(
    case_id: str,
    source: list[str],
    topic: str,
    generated_text: str,
    *,
    call_fn: Callable[[list[str], str, str], tuple[dict, object]] | None = None,
) -> tuple[CaseResult, dict | None]:
    """Runs the source-coverage judge on one Maestro explanation. Returns
    (CaseResult, usage_dict_or_None) - same contract as the other two new judges and the existing
    faithfulness judges.

    Score is a continuous ratio (covered source statements / total source statements) -
    deliberately the mirror of faithfulness's supported-claims/total-claims ratio, since this is
    that same comparison run in the opposite direction (see module docstring). Unlike
    non_contradiction.py's score, a natural denominator exists here (the source material has a
    fixed, enumerable set of statements), so a graded ratio is honest, not a false precision.

    CaseResult.claims is left empty, same reasoning as the other judges: "claim/supported/evidence"
    doesn't fit a coverage record (statement/covered) without stretching the schema's meaning. The
    actual per-statement coverage is in `reason`.

    call_fn is the test-injection point, same role as the other judges' equivalent parameter: when
    supplied, no real Claude call is made - see maestro/judge/shared.py's call_claude_json()
    docstring.
    """

    call = call_fn or _default_call
    parsed, raw_response = call(source, topic, generated_text)

    statements = parsed.get("source_statements", [])
    covered_count = sum(1 for s in statements if s.get("covered"))
    total_count = len(statements)
    score = (covered_count / total_count) if total_count else 1.0  # no source statements -> vacuously covered
    passed = score >= COVERAGE_THRESHOLD

    omitted = [s["statement"] for s in statements if not s.get("covered")]
    detail = (
        f"{covered_count}/{total_count} source statement(s) covered."
        + (f" Omitted: {'; '.join(omitted)}" if omitted else "")
    )

    result = CaseResult(
        case_id=case_id,
        score=score,
        passed=passed,
        reason=EXPERIMENTAL_LABEL + parsed.get("reason", "") + " " + detail,
    )
    usage = usage_from_objects(raw_response) if raw_response is not None else None
    return result, usage
