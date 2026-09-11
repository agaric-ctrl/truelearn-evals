"""CLI: renders a VariantDiff as a styled, side-by-side HTML report - docs/qa-context/COMPARATIVE_AB_TESTING_TASK.md
point 5 ("design the output to be reviewable by a non-engineer... a side-by-side view... not just a
JSON diff"). Same dependency-free HTML/badge-styling approach as
maestro/checks/tier1_content_report.py, for visual consistency with the other report a non-engineer
in this repo already knows how to read.

This file only renders; it never runs a check or a judge itself (see run_variant_pair.py for that)
and it never decides which variant is better (see compare_variants.py's own docstring) - rows where
the two variants disagree are visually flagged so a human's eye goes there first, nothing more.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from maestro.comparative.compare_variants import VariantDiff, compare_variant_results
from maestro.comparative.run_variant_pair import load_variant_result
from maestro.comparative.variants import VariantPair, load_variant_pair


def _check_rows(diff: VariantDiff) -> str:
    rows = []
    for d in diff.check_diffs:
        location = " ".join(part for part in (d.field_name, d.sub_check) if part)
        row_class = "" if d.agrees else "disagree"
        rows.append(
            f'<tr class="{row_class}">'
            f"<td>{html.escape(d.check_name)}</td>"
            f"<td>{html.escape(location)}</td>"
            f"<td>{html.escape(d.variant_a_status or '—')}</td>"
            f"<td>{html.escape(d.variant_b_status or '—')}</td>"
            f'<td>{"agree" if d.agrees else "DISAGREE"}</td>'
            "</tr>"
        )
    return "".join(rows)


def _judge_rows(diff: VariantDiff) -> str:
    rows = []
    for d in diff.judge_diffs:
        row_class = "" if d.agrees else "disagree"

        def _cell(score, passed):
            if score is None and passed is None:
                return "—"
            score_text = f"{score:.2f}" if score is not None else "?"
            passed_text = "PASS" if passed else ("FAIL" if passed is False else "?")
            return f"{passed_text} ({score_text})"

        delta_text = f"{d.score_delta:+.2f}" if d.score_delta is not None else "—"
        rows.append(
            f'<tr class="{row_class}">'
            f"<td>{html.escape(d.judge_name)}</td>"
            f"<td>{html.escape(_cell(d.variant_a_score, d.variant_a_passed))}</td>"
            f"<td>{html.escape(_cell(d.variant_b_score, d.variant_b_passed))}</td>"
            f"<td>{html.escape(delta_text)}</td>"
            f'<td>{"agree" if d.agrees else "DISAGREE"}</td>'
            "</tr>"
        )
    return "".join(rows)


def render_report(pair: VariantPair, diff: VariantDiff) -> str:
    a_html = "<br>".join(
        html.escape(part) for part in (
            pair.variant_a.output.explanation_header, pair.variant_a.output.explanation_footer,
        ) if part
    )
    b_html = "<br>".join(
        html.escape(part) for part in (
            pair.variant_b.output.explanation_header, pair.variant_b.output.explanation_footer,
        ) if part
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maestro Comparative (A/B) Variant Diff Report</title>
<style>
body {{ font: 16px system-ui, sans-serif; margin: 2rem; color: #222; max-width: 1100px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }}
th, td {{ border: 1px solid #ccc; padding: .5rem; text-align: left; vertical-align: top; }}
th {{ background: #f2f2f2; }}
tr.disagree {{ background: #fbe4e4; }}
.summary {{ color: #555; }}
.limitations {{ background: #fff8e6; border: 1px solid #e6c95c; border-radius: .25rem; padding: 1rem 1.5rem; margin-bottom: 1.5rem; }}
.side-by-side {{ display: flex; gap: 1.5rem; margin-bottom: 1.5rem; }}
.side-by-side > div {{ flex: 1; border: 1px solid #ccc; border-radius: .25rem; padding: 1rem; }}
.side-by-side h3 {{ margin-top: 0; }}
</style>
</head>
<body>
<h1>Maestro Comparative (A/B) Variant Diff Report</h1>
<div class="limitations">
<strong>What this is - and is not:</strong> a diff between two independently-checked variants of
the same input, using Tier 1's deterministic checks and whichever Tier 3 judges were run (each
judge is EXPERIMENTAL - validated only against hand-crafted synthetic fixtures, not real SME
judgment). <strong>Nothing here decides which variant is better</strong> - a human reads the
disagreements below (highlighted) and decides what they mean for this specific comparison.
</div>
<p class="summary">Pair: {html.escape(diff.pair_id)} &middot;
Variant A = "{html.escape(diff.variant_a_label)}" &middot;
Variant B = "{html.escape(diff.variant_b_label)}" &middot;
{diff.disagreement_count} disagreement(s) found.</p>

<div class="side-by-side">
<div><h3>Variant A: {html.escape(diff.variant_a_label)}</h3><p>{a_html}</p></div>
<div><h3>Variant B: {html.escape(diff.variant_b_label)}</h3><p>{b_html}</p></div>
</div>

<h2>Tier 1 checks</h2>
<table>
<thead><tr><th>Check</th><th>Location</th><th>Variant A</th><th>Variant B</th><th>Agreement</th></tr></thead>
<tbody>{_check_rows(diff)}</tbody>
</table>

<h2>Tier 3 judges</h2>
<table>
<thead><tr><th>Judge</th><th>Variant A</th><th>Variant B</th><th>Score delta (B - A)</th><th>Agreement</th></tr></thead>
<tbody>{_judge_rows(diff)}</tbody>
</table>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a side-by-side HTML diff report from a variant pair and its two VariantResult files.",
    )
    parser.add_argument("--pair", type=Path, required=True)
    parser.add_argument("--variant-a-eval", type=Path, required=True)
    parser.add_argument("--variant-b-eval", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    pair = load_variant_pair(json.loads(args.pair.read_text(encoding="utf-8")))
    result_a = load_variant_result(json.loads(args.variant_a_eval.read_text(encoding="utf-8")))
    result_b = load_variant_result(json.loads(args.variant_b_eval.read_text(encoding="utf-8")))

    diff = compare_variant_results(pair.pair_id, result_a, result_b)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_report(pair, diff), encoding="utf-8")
    print(f"Wrote {args.out} ({diff.disagreement_count} disagreement(s) found).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
