"""CLI: runs the seven new Tier 1 content checks (docs/qa-context/TIER1_CHECKS_TASK.md) against a
directory of sample or real content and produces a single, styled, human-readable HTML report -
so a non-engineer (SME, editorial) can review what these checks actually catch without reading
code or a raw JSON test report. Same dependency-free HTML approach as tools/html_report.py.

Only runs the seven checks this task added (table_abbreviation_footnotes, teaching_case_standard,
case_numbering, references_format, readability, markdown_structural_compatibility,
density_redundancy, arrow_style) - not the full Tier 1 DEFAULT_CHECKS list. Intended for the
separate manual/scheduled workflow named in the task doc, not the PR-blocking job (which already
runs all of DEFAULT_CHECKS, including these, through test_maestro.py and runner.py).

Content in maestro/examples/tier1_content_samples/*.json is hand-written placeholder data (same
convention as maestro/examples/sample_question.json - parsed via strict GeneratedQuestion(**data)
unpacking, so it can't carry an inline "_placeholder" key; this note is that placeholder
disclaimer instead), not real Maestro output or real TrueLearn content.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from maestro.check_result import CheckResult, Status
from maestro.checks.arrow_style import arrow_style
from maestro.checks.case_numbering import case_numbering
from maestro.checks.density_redundancy import density_redundancy
from maestro.checks.markdown_structural_compatibility import markdown_structural_compatibility
from maestro.checks.readability_check import readability
from maestro.checks.references_format import references_format
from maestro.checks.table_abbreviation_footnotes import table_abbreviation_footnotes
from maestro.checks.teaching_case_standard import teaching_case_standard
from maestro.models import EvalConfig, load_eval_config, load_generated_question

CHECKS = [
    table_abbreviation_footnotes,
    teaching_case_standard,
    case_numbering,
    references_format,
    readability,
    markdown_structural_compatibility,
    density_redundancy,
    arrow_style,
]

_BADGE_CLASS = {Status.PASS: "pass", Status.FAIL: "fail", Status.SKIPPED: "skipped"}
_BADGE_LABEL = {Status.PASS: "PASS", Status.FAIL: "FAIL", Status.SKIPPED: "SKIP"}

_LIMITATIONS = [
    "Case-section and teaching-case boundaries are detected by a “Case N” text-prefix "
    "heuristic (see checks/_case_blocks.py) - real Maestro case markup is unconfirmed.",
    "The table-abbreviation check's false-positive fixes (chemical-formula fragments, "
    "letter+number labels) are a verified, tested heuristic, not a confirmed rule from TrueLearn.",
    "Readability (Flesch-Kincaid grade level) and density/redundancy (n-gram overlap) both ship "
    "with NO default threshold - they report Skipped with the raw score/overlap always visible in "
    "details, until EvalConfig supplies a real target. Any band you configure is illustrative, not "
    "calibrated against real Maestro content or SME judgment.",
    "references_format's citation-type caps and excluded-source checks Skip until EvalConfig names "
    "the actual citation types/sources to check for - the task doc named the rule shape without "
    "naming the specifics.",
    "markdown_structural_compatibility catches formatting-hygiene problems (hard tabs, excess "
    "blank lines, trailing whitespace, malformed code fences) - verified NOT to reliably catch a "
    "single leaked markdown token (e.g. a stray “**”) sitting inline in otherwise-clean "
    "prose, since valid markdown syntax isn't a lint violation by design.",
]


def _load_samples(content_dir: Path) -> list[tuple[str, dict]]:
    samples = []
    for path in sorted(content_dir.glob("*.json")):
        samples.append((path.name, json.loads(path.read_text(encoding="utf-8"))))
    return samples


def _run_checks(question, config: EvalConfig) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in CHECKS:
        results.extend(check(question, config))
    return results


def _render_sample(filename: str, results: list[CheckResult]) -> str:
    rows = []
    for result in results:
        location = " ".join(part for part in (result.field_name, result.sub_check) if part)
        rows.append(
            "<tr>"
            f'<td><span class="badge {_BADGE_CLASS[result.status]}">{_BADGE_LABEL[result.status]}</span></td>'
            f"<td>{html.escape(result.check_name)}</td>"
            f"<td>{html.escape(location)}</td>"
            f"<td>{html.escape(result.message)}</td>"
            "</tr>"
        )

    counts = {status: sum(1 for r in results if r.status == status) for status in Status}
    summary = (
        f"{counts[Status.FAIL]} failed, {counts[Status.SKIPPED]} skipped, "
        f"{counts[Status.PASS]} passed ({len(results)} total)"
    )
    return f"""
<h2>{html.escape(filename)}</h2>
<p class="summary">{summary}</p>
<table>
<thead><tr><th>Status</th><th>Check</th><th>Location</th><th>Message</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
"""


def render_report(samples: list[tuple[str, list[CheckResult]]]) -> str:
    sections = "".join(_render_sample(filename, results) for filename, results in samples)
    limitations = "".join(f"<li>{html.escape(item)}</li>" for item in _LIMITATIONS)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maestro Tier 1 Content Checks Report</title>
<style>
body {{ font: 16px system-ui, sans-serif; margin: 2rem; color: #222; max-width: 900px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }}
th, td {{ border: 1px solid #ccc; padding: .5rem; text-align: left; vertical-align: top; }}
th {{ background: #f2f2f2; }}
.badge {{ display: inline-block; padding: .1rem .5rem; border-radius: .25rem; font-weight: 700; font-size: .85rem; }}
.badge.pass {{ background: #e3f7e8; color: #176b2c; }}
.badge.fail {{ background: #fbe4e4; color: #a21d1d; }}
.badge.skipped {{ background: #eee; color: #555; }}
.summary {{ color: #555; }}
.limitations {{ background: #fff8e6; border: 1px solid #e6c95c; border-radius: .25rem; padding: 1rem 1.5rem; }}
</style>
</head>
<body>
<h1>Maestro Tier 1 Content Checks Report</h1>
<p>Hand-written placeholder sample content (see maestro/examples/tier1_content_samples/), not real
Maestro output or real TrueLearn content. Not wired into any promotion or approval gate.</p>
<div class="limitations">
<strong>Honest limitations - read before trusting a PASS or FAIL below:</strong>
<ul>{limitations}</ul>
</div>
{sections}
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the new Tier 1 content checks against a directory of sample content and "
        "produce a styled HTML report.",
    )
    parser.add_argument(
        "--content-dir", type=Path,
        default=Path(__file__).resolve().parents[1] / "examples" / "tier1_content_samples",
        help="Directory of GeneratedQuestion-shaped JSON files (default: the bundled sample set).",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output path for the HTML report.")
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Path to an EvalConfig JSON file (defaults to all-unconfirmed - every placeholder "
        "threshold Skips rather than guessing).",
    )
    args = parser.parse_args()

    config = (
        load_eval_config(json.loads(args.config.read_text(encoding="utf-8")))
        if args.config else EvalConfig()
    )

    samples = _load_samples(args.content_dir)
    if not samples:
        print(f"No *.json sample files found in {args.content_dir}.")
        return 1

    results_by_sample = [
        (filename, _run_checks(load_generated_question(data), config))
        for filename, data in samples
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_report(results_by_sample), encoding="utf-8")
    print(f"Wrote {args.out} ({len(samples)} sample(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
