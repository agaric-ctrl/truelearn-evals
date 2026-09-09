"""Tests for the golden-set import throughput summary (docs/qa-context/REPORTING_SUMMARY_TASK.md).

Offline only - no live model calls, no golden-dataset-ownership decision needed (per the task doc,
this is orthogonal to that). Covers the pure summarize()/render_markdown() functions directly, plus
one end-to-end integration test proving import_pool.py --outcomes-json and import_summary.py
actually connect (not just that each works in isolation).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from maestro.golden.import_summary import load_outcomes, render_markdown, summarize

ROOT = Path(__file__).resolve().parents[1]


def _outcome(example_id: str, *, promoted: bool, exam_bank: str, reason: str | None = None) -> dict:
    return {
        "example_id": example_id, "display_id": f"R{example_id}", "grade": "approve" if promoted else "reject",
        "promoted": promoted, "reason": reason, "exam_bank": exam_bank,
    }


class SummarizeTests(unittest.TestCase):
    def test_empty_list(self):
        summary = summarize([])
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["promoted"], 0)
        self.assertEqual(summary["blocked"], 0)
        self.assertEqual(summary["by_bank"], {})

    def test_counts_promoted_and_blocked(self):
        outcomes = [
            _outcome("a", promoted=True, exam_bank="USMLE"),
            _outcome("b", promoted=False, exam_bank="USMLE", reason="sme_rejected"),
            _outcome("c", promoted=False, exam_bank="USMLE", reason="tier1_check_failed"),
        ]
        summary = summarize(outcomes)
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["promoted"], 1)
        self.assertEqual(summary["blocked"], 2)

    def test_blocked_reasons_counted_overall(self):
        outcomes = [
            _outcome("a", promoted=False, exam_bank="USMLE", reason="sme_rejected"),
            _outcome("b", promoted=False, exam_bank="COMLEX", reason="sme_rejected"),
            _outcome("c", promoted=False, exam_bank="USMLE", reason="ungraded"),
        ]
        summary = summarize(outcomes)
        self.assertEqual(summary["blocked_by_reason"]["sme_rejected"], 2)
        self.assertEqual(summary["blocked_by_reason"]["ungraded"], 1)

    def test_groups_by_exam_bank(self):
        outcomes = [
            _outcome("a", promoted=True, exam_bank="USMLE"),
            _outcome("b", promoted=True, exam_bank="COMLEX"),
            _outcome("c", promoted=False, exam_bank="COMLEX", reason="sme_rejected"),
        ]
        summary = summarize(outcomes)
        self.assertEqual(set(summary["by_bank"]), {"USMLE", "COMLEX"})
        self.assertEqual(summary["by_bank"]["USMLE"].promoted, 1)
        self.assertEqual(summary["by_bank"]["USMLE"].blocked, 0)
        self.assertEqual(summary["by_bank"]["COMLEX"].promoted, 1)
        self.assertEqual(summary["by_bank"]["COMLEX"].blocked, 1)
        self.assertEqual(summary["by_bank"]["COMLEX"].blocked_by_reason["sme_rejected"], 1)

    def test_missing_exam_bank_grouped_as_unknown_rather_than_dropped(self):
        outcomes = [{"example_id": "a", "display_id": "R1", "grade": "approve", "promoted": True, "reason": None}]
        summary = summarize(outcomes)
        self.assertIn("(unknown bank)", summary["by_bank"])


class RenderMarkdownTests(unittest.TestCase):
    def test_no_outcomes_says_so_plainly(self):
        report = render_markdown(summarize([]))
        self.assertIn("No import runs found", report)

    def test_report_includes_overall_counts_and_bank_table(self):
        outcomes = [
            _outcome("a", promoted=True, exam_bank="USMLE"),
            _outcome("b", promoted=False, exam_bank="USMLE", reason="sme_rejected"),
        ]
        report = render_markdown(summarize(outcomes))
        self.assertIn("**2** row(s) graded", report)
        self.assertIn("**1** promoted", report)
        self.assertIn("**1** blocked", report)
        self.assertIn("Rejected by reviewer", report)  # plain-language label, not the raw reason code
        self.assertIn("| USMLE |", report)

    def test_unknown_reason_falls_back_to_raw_string(self):
        outcomes = [_outcome("a", promoted=False, exam_bank="USMLE", reason="some_future_reason")]
        report = render_markdown(summarize(outcomes))
        self.assertIn("some_future_reason", report)


class LoadOutcomesTests(unittest.TestCase):
    def test_concatenates_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            path_a = tmp_path / "run_a.json"
            path_b = tmp_path / "run_b.json"
            path_a.write_text(json.dumps([_outcome("a", promoted=True, exam_bank="USMLE")]))
            path_b.write_text(json.dumps([_outcome("b", promoted=True, exam_bank="COMLEX")]))

            outcomes = load_outcomes([path_a, path_b])
            self.assertEqual(len(outcomes), 2)
            self.assertEqual({o["example_id"] for o in outcomes}, {"a", "b"})


class CliIntegrationTests(unittest.TestCase):
    def test_help_is_available(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "maestro" / "golden" / "import_summary.py"), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())

    def test_end_to_end_from_a_real_generate_grade_import_run(self):
        """Proves import_pool.py --outcomes-json and import_summary.py actually connect - not just
        that each works against a hand-written fixture in isolation."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            xlsx_path = tmp_path / "pool.xlsx"
            mapping_path = tmp_path / "pool.mapping.json"
            golden_dir = tmp_path / "golden"
            outcomes_path = tmp_path / "outcomes.json"
            summary_path = tmp_path / "summary.md"

            subprocess.run(
                [sys.executable, str(ROOT / "maestro" / "golden" / "generate_pool.py"),
                 "--batch", str(ROOT / "maestro" / "examples" / "sample_golden_batch.jsonl"),
                 "--seed", "1", "--out-xlsx", str(xlsx_path), "--out-mapping", str(mapping_path)],
                capture_output=True, text=True, check=True,
            )

            grade_script = (
                "import openpyxl\n"
                f"wb = openpyxl.load_workbook(r'{xlsx_path}')\n"
                "ws = wb.active\n"
                "headers = [c.value for c in ws[1]]\n"
                "grade_col = headers.index('grade') + 1\n"
                "reviewer_col = headers.index('reviewer_id') + 1\n"
                "for row in range(2, ws.max_row + 1):\n"
                "    ws.cell(row=row, column=grade_col).value = 'approve'\n"
                "    ws.cell(row=row, column=reviewer_col).value = 'ci-smoke'\n"
                f"wb.save(r'{xlsx_path}')\n"
            )
            subprocess.run([sys.executable, "-c", grade_script], check=True)

            subprocess.run(
                [sys.executable, str(ROOT / "maestro" / "golden" / "import_pool.py"),
                 "--graded-xlsx", str(xlsx_path), "--mapping", str(mapping_path),
                 "--golden-dir", str(golden_dir), "--outcomes-json", str(outcomes_path)],
                capture_output=True, text=True, check=True,
            )
            self.assertTrue(outcomes_path.exists())

            result = subprocess.run(
                [sys.executable, str(ROOT / "maestro" / "golden" / "import_summary.py"),
                 "--outcomes-json", str(outcomes_path), "--out", str(summary_path)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(summary_path.exists())

            report = summary_path.read_text(encoding="utf-8")
            self.assertIn("| USMLE |", report)
            self.assertIn("**2** promoted", report)


if __name__ == "__main__":
    unittest.main()
