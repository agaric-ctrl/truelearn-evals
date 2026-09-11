"""Pure diff logic for two already-produced VariantResults - docs/qa-context/COMPARATIVE_AB_TESTING_TASK.md
point 3: this module surfaces disagreement between two variants, it does NOT decide which one is
"better". No scoring/weighting/ranking-across-variants logic of any kind exists anywhere in this
file - only equality and delta reporting, exactly mirroring the same principle already applied to
Tier 2 (SME grading, not an automated verdict).

Has no judge-calling or Tier1-running dependency of its own - like maestro/judge/compare_gold_suites.py,
it only ever consumes two already-produced VariantResult objects, so it runs identically regardless
of which venv(s) actually produced their judge_results (deepeval-only, ragas-only, both, or neither).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from maestro.check_result import CheckResult
from maestro.comparative.run_variant_pair import VariantResult


def _check_key(result: CheckResult) -> tuple[str, str | None, str | None]:
    return (result.check_name, result.field_name, result.sub_check)


@dataclass
class CheckDiff:
    check_name: str
    field_name: str | None
    sub_check: str | None
    variant_a_status: str | None  # None = this check/location didn't fire for variant A at all
    variant_b_status: str | None
    agrees: bool


@dataclass
class JudgeDiff:
    judge_name: str
    variant_a_score: float | None
    variant_a_passed: bool | None
    variant_a_reason: str | None
    variant_b_score: float | None
    variant_b_passed: bool | None
    variant_b_reason: str | None
    score_delta: float | None  # variant_b_score - variant_a_score, when both are scored
    agrees: bool  # same passed verdict on both sides; None-vs-anything never counts as agreeing


@dataclass
class VariantDiff:
    pair_id: str
    variant_a_label: str
    variant_b_label: str
    check_diffs: list[CheckDiff] = field(default_factory=list)
    judge_diffs: list[JudgeDiff] = field(default_factory=list)

    @property
    def disagreement_count(self) -> int:
        return (
            sum(1 for d in self.check_diffs if not d.agrees)
            + sum(1 for d in self.judge_diffs if not d.agrees)
        )


def compare_variant_results(pair_id: str, result_a: VariantResult, result_b: VariantResult) -> VariantDiff:
    """Aligns each variant's Tier 1 results by (check_name, field_name, sub_check) - the two
    variants are different content, so they won't always produce the exact same number of results
    (e.g. a variant with more tables produces more per-table rows); a check/location present on
    only one side is reported with the other side as None rather than silently dropped or crashing.
    """

    checks_a = {_check_key(r): r for r in result_a.tier1_results}
    checks_b = {_check_key(r): r for r in result_b.tier1_results}
    all_keys = sorted(
        set(checks_a) | set(checks_b),
        key=lambda k: (k[0], k[1] or "", k[2] or ""),
    )

    check_diffs = []
    for key in all_keys:
        check_name, field_name, sub_check = key
        item_a = checks_a.get(key)
        item_b = checks_b.get(key)
        status_a = item_a.status.value if item_a else None
        status_b = item_b.status.value if item_b else None
        check_diffs.append(
            CheckDiff(
                check_name=check_name, field_name=field_name, sub_check=sub_check,
                variant_a_status=status_a, variant_b_status=status_b,
                agrees=(status_a == status_b),
            )
        )

    all_judge_names = sorted(set(result_a.judge_results) | set(result_b.judge_results))
    judge_diffs = []
    for name in all_judge_names:
        judge_a = result_a.judge_results.get(name)
        judge_b = result_b.judge_results.get(name)
        score_a = judge_a.score if judge_a else None
        score_b = judge_b.score if judge_b else None
        passed_a = judge_a.passed if judge_a else None
        passed_b = judge_b.passed if judge_b else None
        judge_diffs.append(
            JudgeDiff(
                judge_name=name,
                variant_a_score=score_a, variant_a_passed=passed_a,
                variant_a_reason=judge_a.reason if judge_a else None,
                variant_b_score=score_b, variant_b_passed=passed_b,
                variant_b_reason=judge_b.reason if judge_b else None,
                score_delta=(score_b - score_a) if (score_a is not None and score_b is not None) else None,
                agrees=(passed_a is not None and passed_a == passed_b),
            )
        )

    return VariantDiff(
        pair_id=pair_id,
        variant_a_label=result_a.label, variant_b_label=result_b.label,
        check_diffs=check_diffs, judge_diffs=judge_diffs,
    )
