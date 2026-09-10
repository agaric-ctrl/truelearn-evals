"""CLI: runs Tier 1's existing content checks against real, full reference articles (.docx) -
per docs/qa-context/EDITORIAL_ASSETS_STAGING_TASK.md step 3. Real validation against real,
already-approved content - not gated on golden-dataset ownership or SME assignment, since this
just runs existing deterministic checks and reports what they find.

CONTENT-SHAPE DECISION, stated explicitly: an article has no natural stem/header/footer/bottom-line
split the way a GeneratedQuestion does. The article's full body (everything between its own title
and the References section - see docx_convert.py) is placed entirely into explanation_footer,
which is where every one of Tier 1's new checks already expects case/table/density content to
live; question_text/explanation_header/bottom_line are left empty (correctly Skipped by the
checks that key on them). The article's References section becomes GeneratedQuestion.references.

HONESTY NOTE, carried into the report itself: this proves the checks work and shows what they find
on real content - it is NOT a statement about Editorial's overall content quality from 3 articles,
and some findings below may reflect a check's own calibration gap (e.g. a sentence-ceiling or
footnote-row assumption that doesn't match real house style) rather than a defect in the article.
Read the findings, don't just count the FAILs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from maestro.checks.tier1_content_report import CHECKS, render_report
from maestro.golden.docx_convert import convert_docx
from maestro.models import EvalConfig, GeneratedQuestion


def article_to_generated_question(path: Path) -> GeneratedQuestion:
    article = convert_docx(path)
    return GeneratedQuestion(
        unique_name=article.title or path.stem,
        explanation_footer=article.body_html,
        references=article.references,
    )


def _run_checks(question: GeneratedQuestion, config: EvalConfig) -> list:
    results = []
    for check in CHECKS:
        results.extend(check(question, config))
    return results


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run Tier 1's content checks against real, full reference .docx articles.",
    )
    parser.add_argument("--reference-articles", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True, help="Output path for the HTML report.")
    parser.add_argument(
        "--save-converted-json", type=Path, default=None,
        help="Optional: also save each article's GeneratedQuestion-shaped JSON here (for reuse "
        "with maestro/checks/tier1_content_report.py's own --content-dir flag).",
    )
    args = parser.parse_args()

    config = EvalConfig()
    samples = []
    for path in args.reference_articles:
        question = article_to_generated_question(path)
        samples.append((path.name, _run_checks(question, config)))

        if args.save_converted_json:
            args.save_converted_json.mkdir(parents=True, exist_ok=True)
            from dataclasses import asdict
            out_path = args.save_converted_json / f"{path.stem}.json"
            out_path.write_text(json.dumps(asdict(question), indent=2), encoding="utf-8")

    intro = (
        "Real, full reference articles (.docx) from Editorial's Biochemistry asset bundle - not "
        "placeholder or synthetic content. See docs/qa-context/EDITORIAL_ASSETS_STAGING_TASK.md - "
        "this is a draft validation run, not an adopted golden dataset or an approval gate."
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_report(samples, intro=intro), encoding="utf-8")

    total_fails = sum(1 for _, results in samples for r in results if r.status.value == "fail")
    print(f"Wrote {args.out} ({len(samples)} article(s), {total_fails} FAIL(s) total across all checks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
