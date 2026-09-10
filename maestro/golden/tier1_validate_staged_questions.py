"""CLI: runs Tier 1's content checks (the same CHECKS list as tier1_content_report.py) against a
directory of staged question drafts - GoldenExample-shaped JSON files, as produced by
stage_editorial_assets.py under maestro/golden_data/staging/<bank>/questions/ - and produces the
same styled HTML report.

This is the question-side counterpart to tier1_validate_articles.py (which does the same thing for
whole reference articles). Neither is wired into any promotion/approval gate: these are draft
proposals (see docs/qa-context/EDITORIAL_ASSETS_STAGING_TASK.md), not adopted golden data.

SHAPE NOTE: a staged question file is GoldenExample-shaped - {"expected": {...GeneratedQuestion
fields...}, "tags": [...], ...} - not directly GeneratedQuestion-shaped at the top level, unlike
tier1_content_report.py's --content-dir input. This script unwraps "expected" before handing the
question to the existing checks; nothing about the checks themselves changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from maestro.checks.tier1_content_report import CHECKS, render_report
from maestro.models import EvalConfig, load_eval_config, load_generated_question


def _run_checks(question, config: EvalConfig) -> list:
    results = []
    for check in CHECKS:
        results.extend(check(question, config))
    return results


def _describe(data: dict) -> str:
    """Builds a human-readable subtitle from the staged file's own real metadata (exam_bank,
    input.topic, tier: tag) so a reader can tell what a sample actually is without opening the
    JSON - stage_editorial_assets.py already put all of this there for exactly this purpose."""
    parts = []
    if data.get("exam_bank"):
        parts.append(data["exam_bank"])
    tier = next((tag.split(":", 1)[1] for tag in data.get("tags", []) if tag.startswith("tier:")), None)
    if tier:
        parts.append(f"tier: {tier}")
    topic = (data.get("input") or {}).get("topic")
    if topic:
        parts.append(f'topic: "{topic}"')
    return " | ".join(parts)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run Tier 1's content checks against staged (GoldenExample-shaped) question "
        "drafts and produce a styled HTML report.",
    )
    parser.add_argument("--questions-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Output path for the HTML report.")
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Path to an EvalConfig JSON file (defaults to all-unconfirmed).",
    )
    args = parser.parse_args()

    config = (
        load_eval_config(json.loads(args.config.read_text(encoding="utf-8")))
        if args.config else EvalConfig()
    )

    paths = sorted(args.questions_dir.glob("*.json"))
    if not paths:
        print(f"No *.json staged question files found in {args.questions_dir}.")
        return 1

    samples = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        question = load_generated_question(data["expected"])
        title = data.get("example_id", path.stem)
        subtitle = _describe(data)
        samples.append((title, _run_checks(question, config), subtitle))

    intro = (
        "Real staged question drafts, tiered (adversarial / known_hard / best_in_class) from "
        "Editorial's real Biochemistry question bank - not placeholder or synthetic content. See "
        "docs/qa-context/EDITORIAL_ASSETS_STAGING_TASK.md - this is a draft validation run, not an "
        "adopted golden dataset or an approval gate."
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_report(samples, intro=intro), encoding="utf-8")

    total_fails = sum(1 for _, results, _subtitle in samples for r in results if r.status.value == "fail")
    print(f"Wrote {args.out} ({len(samples)} question(s), {total_fails} FAIL(s) total across all checks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
