"""Comparative (A/B) testing scaffold: the comparison runner - docs/qa-context/COMPARATIVE_AB_TESTING_TASK.md
point 2. Runs Tier 1's DEFAULT_CHECKS and every available Tier 3 judge against EACH variant in a
pair INDEPENDENTLY (never comparing them to each other mid-run) - the diff itself is computed
afterward, by compare_variants.py, from the two already-produced results. This module never decides
which variant is better; see maestro/comparative/__init__.py.

WHY NO SINGLE VENV RUNS ALL FIVE TIER 3 JUDGES: deepeval and ragas conflict on the click dependency
and live in separate venvs (requirements-maestro.txt vs requirements-maestro-ragas.txt) - the same
constraint every other Tier 3 script in this repo already lives with (see judge/faithfulness_ragas.py's
docstring). _available_judges() auto-detects whichever judges the CURRENT process can import rather
than assuming all five; running this CLI once per venv and merging into the same --out-a/--out-b
files (see merge_variant_result() below) is how full Tier 3 coverage actually gets assembled -
exactly mirroring how this repo's CI already runs deepeval/ragas/Promptfoo tests in separate jobs
and combines their output afterward (judge/compare_gold_suites.py). Promptfoo itself isn't a Python
function at all (it's a Node/YAML CLI tool) - its already-produced, normalized JSON output can be
folded in via --promptfoo-result-a/--promptfoo-result-b, the same "never run it, only consume its
output" convention compare_gold_suites.py already uses for Promptfoo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from maestro.check_result import CheckResult, Status
from maestro.comparative.variants import Variant, VariantPair, load_variant_pair
from maestro.judge.shared import build_actual_output
from maestro.models import EvalConfig, load_eval_config
from tools.eval_result import CaseResult

# Tier 1 (maestro.runner -> maestro.checks -> lxml) is deliberately NOT importable in
# .venv-maestro-ragas - that venv only ever installs what faithfulness_ragas.py/test_judge_ragas.py
# need (see requirements-maestro-ragas.txt's own comment), the same way it never installs deepeval.
# Guarded the same way _available_judges() below guards each individual judge import, so running
# this CLI from that venv (to add just the ragas judge's contribution) degrades gracefully instead
# of crashing at import time.
try:
    from maestro.runner import run_checks
    _TIER1_AVAILABLE = True
except ImportError:
    run_checks = None
    _TIER1_AVAILABLE = False

JudgeCallable = Callable[[str, list[str], str, str], tuple[CaseResult, Optional[dict]]]


@dataclass
class VariantResult:
    label: str
    tier1_results: list[CheckResult] = field(default_factory=list)
    judge_results: dict[str, CaseResult] = field(default_factory=dict)


def evaluate_variant(
    variant: Variant, topic: str, config: EvalConfig, judges: dict[str, JudgeCallable],
) -> VariantResult:
    """Runs Tier 1 + every supplied Tier 3 judge against one variant's output. `judges` is an
    explicit, caller-supplied mapping (name -> callable) rather than a hardcoded list - real CLI
    usage passes whatever _available_judges() finds importable; tests pass hand-built fakes so this
    function's own orchestration logic (not any judge's real verdict) is what gets verified offline.
    """

    tier1_results = run_checks(variant.output, config).results if _TIER1_AVAILABLE else []
    generated_text = build_actual_output(
        variant.output.explanation_header, variant.output.explanation_footer, variant.output.bottom_line,
    )
    judge_results = {}
    for name, judge_fn in judges.items():
        result, _usage = judge_fn(variant.label, variant.source, topic, generated_text)
        judge_results[name] = result
    return VariantResult(label=variant.label, tier1_results=tier1_results, judge_results=judge_results)


def merge_variant_result(existing: VariantResult, new: VariantResult) -> VariantResult:
    """Combines a freshly-computed VariantResult into a previously-saved one from a different venv
    run. judge_results is a dict update so judges found in `new` add to (never silently drop)
    whatever judges an earlier venv's run already contributed.

    tier1_results: replaced with the fresh copy ONLY when `new` actually has one. Tier 1 itself
    doesn't depend on which venv runs it, EXCEPT .venv-maestro-ragas, which deliberately never
    installs Tier 1's dependencies (see _TIER1_AVAILABLE above) - a run from that venv produces an
    empty tier1_results, and blindly overwriting with that would silently erase real, already-saved
    Tier 1 results from an earlier .venv-maestro run. An empty `new.tier1_results` is therefore
    treated as "this run didn't touch Tier 1", not as "Tier 1 now has zero findings".
    """

    if new.tier1_results:
        existing.tier1_results = new.tier1_results
    existing.judge_results.update(new.judge_results)
    return existing


def variant_result_to_dict(result: VariantResult) -> dict:
    return {
        "label": result.label,
        "tier1_results": [asdict(r) for r in result.tier1_results],
        "judge_results": {name: asdict(r) for name, r in result.judge_results.items()},
    }


def load_variant_result(data: dict) -> VariantResult:
    tier1_results = [
        CheckResult(
            check_name=r["check_name"], status=Status(r["status"]), message=r["message"],
            field_name=r.get("field_name"), sub_check=r.get("sub_check"), details=r.get("details", {}),
        )
        for r in data.get("tier1_results", [])
    ]
    judge_results = {
        name: CaseResult(
            case_id=r["case_id"], score=r.get("score"), passed=r.get("passed"),
            reason=r.get("reason"), claims=r.get("claims", []),
        )
        for name, r in data.get("judge_results", {}).items()
    }
    return VariantResult(label=data["label"], tier1_results=tier1_results, judge_results=judge_results)


def _available_judges() -> dict[str, JudgeCallable]:
    """Auto-detects which Tier 3 judges the CURRENT process can import - see module docstring for
    why this is never a fixed list of all five. Each try/except is a real, deliberate capability
    probe (importing a package, not calling it - no API key or network access needed to reach this
    point), not a fallback-on-error pattern."""

    judges: dict[str, JudgeCallable] = {}

    try:
        from maestro.judge.non_contradiction import judge_non_contradiction
        judges["non_contradiction"] = judge_non_contradiction
    except ImportError:
        pass

    try:
        # EXAM QUESTIONS ONLY - see source_coverage.py's SCOPE section. If the variant pair holds
        # ARTICLE content (which tier1_validate_articles.py's conversion makes look exactly like a
        # question to this code), drop this judge from the returned dict: source-coverage fails
        # every article by design and its score here would be meaningless.
        from maestro.judge.source_coverage import judge_source_coverage
        judges["source_coverage"] = judge_source_coverage
    except ImportError:
        pass

    try:
        from maestro.judge.faithfulness import judge_faithfulness
        judges["faithfulness_deepeval"] = judge_faithfulness
    except ImportError:
        pass

    try:
        from maestro.judge.faithfulness_ragas import judge_faithfulness_ragas

        def _ragas_sync(case_id: str, source: list[str], topic: str, text: str):
            return asyncio.run(judge_faithfulness_ragas(case_id, source, topic, text))

        judges["faithfulness_ragas"] = _ragas_sync
    except ImportError:
        pass

    return judges


def _fold_in_promptfoo_result(result: VariantResult, promptfoo_path: Path | None) -> None:
    if promptfoo_path is None:
        return
    data = json.loads(promptfoo_path.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if not cases:
        return
    case = cases[0]
    result.judge_results["promptfoo"] = CaseResult(
        case_id=case["case_id"], score=case.get("score"), passed=case.get("passed"),
        reason=case.get("reason"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Tier 1 checks and available Tier 3 judges against both sides of a variant pair.",
    )
    parser.add_argument("--pair", type=Path, required=True, help="Path to a VariantPair JSON file.")
    parser.add_argument("--config", type=Path, default=None, help="Path to an EvalConfig JSON file.")
    parser.add_argument("--out-a", type=Path, required=True)
    parser.add_argument("--out-b", type=Path, required=True)
    parser.add_argument(
        "--promptfoo-result-a", type=Path, default=None,
        help="Already-produced, normalized Promptfoo EvaluationResult JSON for variant A (never run here).",
    )
    parser.add_argument("--promptfoo-result-b", type=Path, default=None)
    args = parser.parse_args()

    pair: VariantPair = load_variant_pair(json.loads(args.pair.read_text(encoding="utf-8")))
    config = (
        load_eval_config(json.loads(args.config.read_text(encoding="utf-8")))
        if args.config else EvalConfig()
    )
    topic = pair.input.get("topic", "")

    judges = _available_judges()
    print(
        f"Tier 1 {'available' if _TIER1_AVAILABLE else 'NOT available'} in this venv. "
        f"Running with {len(judges)} available Tier 3 judge(s): {sorted(judges)}",
        file=sys.stderr,
    )
    if not _TIER1_AVAILABLE:
        print(
            "WARNING: Tier 1 is not importable in this venv (expected in .venv-maestro-ragas - see "
            "this file's module docstring). This run will only contribute judge results; existing "
            "Tier 1 results at --out-a/--out-b, if any, are preserved, not overwritten.",
            file=sys.stderr,
        )
    if not judges:
        print(
            "WARNING: no Tier 3 judges importable in this venv - only Tier 1 will run this time. "
            "Run again from .venv-maestro and/or .venv-maestro-ragas (same --out-a/--out-b paths) "
            "to add judge coverage - see this file's module docstring.",
            file=sys.stderr,
        )

    for variant, promptfoo_path, out_path in (
        (pair.variant_a, args.promptfoo_result_a, args.out_a),
        (pair.variant_b, args.promptfoo_result_b, args.out_b),
    ):
        result = evaluate_variant(variant, topic, config, judges)
        _fold_in_promptfoo_result(result, promptfoo_path)

        if out_path.exists():
            existing = load_variant_result(json.loads(out_path.read_text(encoding="utf-8")))
            result = merge_variant_result(existing, result)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(variant_result_to_dict(result), indent=2), encoding="utf-8")
        fail_count = sum(1 for r in result.tier1_results if r.status == Status.FAIL)
        print(f"Wrote {out_path} ({len(result.judge_results)} judge result(s), {fail_count} Tier 1 FAIL(s)).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
