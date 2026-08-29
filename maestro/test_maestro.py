"""Tests for the Maestro generated-question check harness.

Ported 1:1 from the original C# xUnit suite (26 tests across required_fields_present,
field_constraints, html_well_formed, tables_no_duplicates), plus new tests for behavior added
during the Python port: the unique_name fix in required_fields_present, the
allowed_question_formats_by_type sub-check in field_constraints, and coverage for the two stub
checks and the schema/runner that had no dedicated C# tests.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from maestro.check_result import CheckResult, QuestionCheckReport, Status, render_summary
from maestro.checks.field_constraints import field_constraints
from maestro.checks.html_well_formed import html_well_formed
from maestro.checks.references_format import references_format
from maestro.checks.required_fields_present import required_fields_present
from maestro.checks.tables_no_duplicates import tables_no_duplicates
from maestro.checks.tables_placement_valid import tables_placement_valid
from maestro.models import EvalConfig, GeneratedQuestion, TablePlacementConfig
from maestro.runner import run_checks

ROOT = Path(__file__).resolve().parents[1]


def _single(results: list[CheckResult], field_name: str | None = None, sub_check: str | None = None) -> CheckResult:
    matches = [
        result for result in results
        if (field_name is None or result.field_name == field_name)
        and (sub_check is None or result.sub_check == sub_check)
    ]
    assert len(matches) == 1, f"expected exactly 1 match, got {len(matches)}: {matches}"
    return matches[0]


# ---------------------------------------------------------------------------
# required_fields_present.py - ported from RequiredFieldsCheckTests.cs (5 original + nbsp fix)
# ---------------------------------------------------------------------------

class RequiredFieldsPresentTests(unittest.TestCase):
    @staticmethod
    def _good_question() -> GeneratedQuestion:
        return GeneratedQuestion(
            unique_name="Test_Question_001",
            question_text="<p>A 45-year-old presents with...</p>",
            explanation_header="<p>The correct answer is B.</p>",
            explanation_footer="<p>Reviewed 2026.</p>",
        )

    def test_all_required_fields_present_all_pass(self):
        results = required_fields_present(self._good_question(), EvalConfig())
        for result in results:
            if result.field_name == "bottom_line":
                continue  # bottom_line's rule is unconfirmed by default -> Skipped, not Pass
            self.assertEqual(result.status, Status.PASS, result.message)

    def test_missing_question_text_fails(self):
        question = self._good_question()
        question.question_text = ""
        result = _single(required_fields_present(question, EvalConfig()), "question_text")
        self.assertEqual(result.status, Status.FAIL)

    def test_empty_tags_only_counts_as_missing(self):
        question = self._good_question()
        question.explanation_header = "<p></p>"
        result = _single(required_fields_present(question, EvalConfig()), "explanation_header")
        self.assertEqual(result.status, Status.FAIL)

    def test_nbsp_only_counts_as_missing(self):
        """Regression test for the bug found in review: a naive tag-stripping regex leaves the
        literal text "&nbsp;" behind and misreads the field as non-empty."""
        question = self._good_question()
        question.explanation_header = "<p>&nbsp;</p>"
        result = _single(required_fields_present(question, EvalConfig()), "explanation_header")
        self.assertEqual(result.status, Status.FAIL)

    def test_bottom_line_skipped_when_rule_unconfirmed(self):
        result = _single(
            required_fields_present(self._good_question(), EvalConfig(require_bottom_line=None)),
            "bottom_line",
        )
        self.assertEqual(result.status, Status.SKIPPED)

    def test_bottom_line_fails_when_required_and_missing(self):
        question = self._good_question()
        question.bottom_line = None
        result = _single(
            required_fields_present(question, EvalConfig(require_bottom_line=True)), "bottom_line",
        )
        self.assertEqual(result.status, Status.FAIL)

    def test_bottom_line_passes_regardless_when_not_required(self):
        question = self._good_question()
        question.bottom_line = None
        result = _single(
            required_fields_present(question, EvalConfig(require_bottom_line=False)), "bottom_line",
        )
        self.assertEqual(result.status, Status.PASS)

    def test_missing_unique_name_fails(self):
        """New beyond the C# original: unique_name is now unconditionally required here, closing
        a gap where field_constraints claimed unique-name-emptiness was "covered by
        required_fields_present" but nothing actually enforced it."""
        question = self._good_question()
        question.unique_name = ""
        result = _single(required_fields_present(question, EvalConfig()), "unique_name")
        self.assertEqual(result.status, Status.FAIL)


# ---------------------------------------------------------------------------
# field_constraints.py - ported from FieldConstraintsCheckTests.cs (10 original) + 4 new
# ---------------------------------------------------------------------------

class FieldConstraintsTests(unittest.TestCase):
    @staticmethod
    def _good_question() -> GeneratedQuestion:
        return GeneratedQuestion(
            unique_name="Cardio_MI_001",
            main_topic="Cardiology",
            modifier="Adult",
            question_type="single question",
            question_format="Text",
        )

    def test_well_formed_item_all_applicable_checks_pass(self):
        results = field_constraints(self._good_question(), EvalConfig())
        for result in results:
            if result.status is Status.SKIPPED:
                continue
            self.assertEqual(result.status, Status.PASS, result.message)

    def test_unique_name_at_exactly_50_chars_passes(self):
        question = self._good_question()
        question.unique_name = "a" * 50
        result = _single(field_constraints(question, EvalConfig()), sub_check="unique_name_length")
        self.assertEqual(result.status, Status.PASS)

    def test_unique_name_over_50_chars_fails(self):
        question = self._good_question()
        question.unique_name = "a" * 51
        result = _single(field_constraints(question, EvalConfig()), sub_check="unique_name_length")
        self.assertEqual(result.status, Status.FAIL)

    def test_unique_name_with_space_fails(self):
        question = self._good_question()
        question.unique_name = "Cardio MI 001"
        result = _single(field_constraints(question, EvalConfig()), sub_check="unique_name_no_whitespace")
        self.assertEqual(result.status, Status.FAIL)

    def test_unique_name_already_in_corpus_fails(self):
        question = self._good_question()
        config = EvalConfig(existing_unique_names={question.unique_name})
        result = _single(field_constraints(question, config), sub_check="unique_name_uniqueness")
        self.assertEqual(result.status, Status.FAIL)

    def test_unique_name_uniqueness_skipped_without_corpus(self):
        result = _single(
            field_constraints(self._good_question(), EvalConfig()), sub_check="unique_name_uniqueness",
        )
        self.assertEqual(result.status, Status.SKIPPED)

    def test_slash_in_main_topic_fails(self):
        question = self._good_question()
        question.main_topic = "Cardio/Pulm"
        result = _single(field_constraints(question, EvalConfig()), sub_check="main_topic_no_path_separators")
        self.assertEqual(result.status, Status.FAIL)

    def test_backslash_in_modifier_fails(self):
        question = self._good_question()
        question.modifier = "Adult\\Pediatric"
        result = _single(field_constraints(question, EvalConfig()), sub_check="modifier_no_path_separators")
        self.assertEqual(result.status, Status.FAIL)

    def test_single_question_type_missing_format_fails(self):
        question = self._good_question()
        question.question_format = ""
        result = _single(
            field_constraints(question, EvalConfig()), sub_check="question_format_required_for_single",
        )
        self.assertEqual(result.status, Status.FAIL)

    def test_non_single_question_type_missing_format_skipped(self):
        question = self._good_question()
        question.question_type = "multipart"
        question.question_format = ""
        result = _single(
            field_constraints(question, EvalConfig()), sub_check="question_format_required_for_single",
        )
        self.assertEqual(result.status, Status.SKIPPED)

    # New sub-check beyond the C# original: allowed_question_formats_by_type was declared in
    # EvalConfig there but never wired into any check - a real doc/code mismatch fixed in this port.

    def test_allowed_formats_skipped_when_config_empty(self):
        result = _single(
            field_constraints(self._good_question(), EvalConfig()),
            sub_check="question_format_allowed_for_question_type",
        )
        self.assertEqual(result.status, Status.SKIPPED)

    def test_allowed_formats_skipped_when_type_not_configured(self):
        config = EvalConfig(allowed_question_formats_by_type={"multipart": {"Text"}})
        result = _single(
            field_constraints(self._good_question(), config),
            sub_check="question_format_allowed_for_question_type",
        )
        self.assertEqual(result.status, Status.SKIPPED)

    def test_allowed_formats_passes_when_format_allowed(self):
        config = EvalConfig(allowed_question_formats_by_type={"single question": {"Text", "Image"}})
        result = _single(
            field_constraints(self._good_question(), config),
            sub_check="question_format_allowed_for_question_type",
        )
        self.assertEqual(result.status, Status.PASS)

    def test_allowed_formats_fails_when_format_not_allowed(self):
        config = EvalConfig(allowed_question_formats_by_type={"single question": {"Image"}})
        result = _single(
            field_constraints(self._good_question(), config),
            sub_check="question_format_allowed_for_question_type",
        )
        self.assertEqual(result.status, Status.FAIL)


# ---------------------------------------------------------------------------
# html_well_formed.py - ported from HtmlWellFormedCheckTests.cs (3)
# ---------------------------------------------------------------------------

class HtmlWellFormedTests(unittest.TestCase):
    def test_well_formed_html_passes(self):
        question = GeneratedQuestion(question_text="<p>A patient presents with <strong>fever</strong>.</p>")
        result = _single(html_well_formed(question, EvalConfig()), "question_text")
        self.assertEqual(result.status, Status.PASS)

    def test_mismatched_crossing_tags_fail(self):
        """The C# original's example for this test was a plain unclosed tag
        ("<table><tr><td>Value", no closing tags at all). Verified empirically against lxml's real
        parser (not assumed): libxml2's HTML mode auto-closes a tag left open at end-of-input,
        exactly like a browser would - that's correct HTML5 behavior, not a defect, so it does NOT
        raise here. What it DOES reliably flag is a genuine structural error: crossing/mismatched
        tags. Swapped the example to one that's actually a syntax error under this check's real,
        verified semantics."""
        question = GeneratedQuestion(question_text="<p><b>bold</p></b>")
        result = _single(html_well_formed(question, EvalConfig()), "question_text")
        self.assertEqual(result.status, Status.FAIL)

    def test_unclosed_tag_at_end_of_input_is_not_flagged(self):
        """Documents the verified boundary from the test above: an implicitly-closed tag is valid
        HTML5, not broken markup, so this check intentionally passes it."""
        question = GeneratedQuestion(question_text="<table><tr><td>Value")
        result = _single(html_well_formed(question, EvalConfig()), "question_text")
        self.assertEqual(result.status, Status.PASS)

    def test_empty_field_skipped(self):
        question = GeneratedQuestion(explanation_header="")
        result = _single(html_well_formed(question, EvalConfig()), "explanation_header")
        self.assertEqual(result.status, Status.SKIPPED)


# ---------------------------------------------------------------------------
# tables_no_duplicates.py - ported from TablesNoDuplicatesCheckTests.cs (7)
# ---------------------------------------------------------------------------

class TablesNoDuplicatesTests(unittest.TestCase):
    def test_no_tables_skipped(self):
        question = GeneratedQuestion(question_text="<p>No tables here.</p>")
        results = tables_no_duplicates(question, EvalConfig())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.SKIPPED)

    def test_one_table_passes(self):
        question = GeneratedQuestion(question_text="<table><tr><td>Na</td><td>140</td></tr></table>")
        results = tables_no_duplicates(question, EvalConfig())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.PASS)

    def test_same_table_repeated_within_one_field_fails(self):
        table = "<table><tr><td>Na</td><td>140</td></tr></table>"
        question = GeneratedQuestion(question_text=table + table)
        results = tables_no_duplicates(question, EvalConfig())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.FAIL)

    def test_same_table_copied_across_two_fields_fails(self):
        table = "<table><tr><td>Na</td><td>140</td></tr></table>"
        question = GeneratedQuestion(question_text=table, explanation_header=table)
        results = tables_no_duplicates(question, EvalConfig())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.FAIL)
        self.assertIn("question_text", results[0].message)
        self.assertIn("explanation_header", results[0].message)

    def test_same_table_pretty_printed_vs_minified_still_counts_as_duplicate(self):
        question = GeneratedQuestion(
            question_text="<table><tr><td>Na</td><td>140</td></tr></table>",
            explanation_header="<table>\n  <tr>\n    <td>Na</td>\n    <td>140</td>\n  </tr>\n</table>",
        )
        results = tables_no_duplicates(question, EvalConfig())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.FAIL)

    def test_different_cell_split_same_concatenated_text_not_a_duplicate(self):
        """"Na140" as one cell is a different table from "Na" and "140" as two cells, even though
        naive whitespace-collapsed text would read the same either way."""
        question = GeneratedQuestion(
            question_text="<table><tr><td>Na140</td></tr></table>",
            explanation_header="<table><tr><td>Na</td><td>140</td></tr></table>",
        )
        results = tables_no_duplicates(question, EvalConfig())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.PASS)

    def test_two_different_tables_passes(self):
        question = GeneratedQuestion(
            question_text="<table><tr><td>Na</td><td>140</td></tr></table>",
            explanation_header="<table><tr><td>K</td><td>4.0</td></tr></table>",
        )
        results = tables_no_duplicates(question, EvalConfig())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.PASS)


# ---------------------------------------------------------------------------
# tables_placement_valid.py - new coverage, no C# test file existed for this stub
# ---------------------------------------------------------------------------

class TablesPlacementValidTests(unittest.TestCase):
    def test_skipped_when_unconfirmed(self):
        results = tables_placement_valid(GeneratedQuestion(), EvalConfig())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.SKIPPED)

    def test_fails_when_confirmed_but_not_implemented(self):
        config = EvalConfig(table_placement=TablePlacementConfig(confirmed=True))
        results = tables_placement_valid(GeneratedQuestion(), config)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.FAIL)


# ---------------------------------------------------------------------------
# references_format.py - new coverage, no C# test file existed for this stub
# ---------------------------------------------------------------------------

class ReferencesFormatTests(unittest.TestCase):
    def test_skipped_when_pattern_unset(self):
        question = GeneratedQuestion(references=["Smith et al., 2020"])
        results = references_format(question, EvalConfig())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.SKIPPED)

    def test_passes_when_no_references(self):
        config = EvalConfig(reference_style_pattern=r"[A-Z][a-z]+ et al\., \d{4}")
        results = references_format(GeneratedQuestion(references=[]), config)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.PASS)

    def test_each_reference_checked_independently(self):
        config = EvalConfig(reference_style_pattern=r"[A-Z][a-z]+ et al\., \d{4}")
        question = GeneratedQuestion(references=["Smith et al., 2020", "not styled correctly"])
        results = references_format(question, config)
        self.assertEqual(len(results), 2)
        with self.subTest(reference=0):
            self.assertEqual(results[0].status, Status.PASS)
        with self.subTest(reference=1):
            self.assertEqual(results[1].status, Status.FAIL)


# ---------------------------------------------------------------------------
# check_result.py - new schema coverage
# ---------------------------------------------------------------------------

class CheckResultSchemaTests(unittest.TestCase):
    def test_to_json_round_trip(self):
        import json

        report = QuestionCheckReport(
            unique_name="Test_001",
            results=[CheckResult(check_name="x", status=Status.FAIL, message="broken")],
        )
        decoded = json.loads(report.to_json())
        self.assertEqual(decoded["unique_name"], "Test_001")
        self.assertEqual(decoded["results"][0]["status"], "fail")

    def test_render_summary_orders_fail_before_skipped_before_pass(self):
        report = QuestionCheckReport(
            unique_name="Test_001",
            results=[
                CheckResult(check_name="a", status=Status.PASS, message="ok"),
                CheckResult(check_name="b", status=Status.SKIPPED, message="unconfirmed"),
                CheckResult(check_name="c", status=Status.FAIL, message="broken"),
            ],
        )
        lines = [line for line in render_summary(report).splitlines() if line.startswith("[")]
        statuses = [line.split("]")[0][1:] for line in lines]
        self.assertEqual(statuses, ["FAIL", "SKIPPED", "PASS"])


# ---------------------------------------------------------------------------
# runner.py - new runner coverage
# ---------------------------------------------------------------------------

class RunnerTests(unittest.TestCase):
    def test_run_checks_aggregates_all_default_checks(self):
        question = GeneratedQuestion(
            unique_name="Test_Question_001",
            question_text="<p>Stem.</p>",
            explanation_header="<p>Answer.</p>",
            explanation_footer="<p>Footer.</p>",
        )
        report = run_checks(question, EvalConfig())
        check_names = {result.check_name for result in report.results}
        self.assertEqual(
            check_names,
            {
                "required_fields_present", "field_constraints", "html_well_formed",
                "tables_no_duplicates", "tables_placement_valid", "references_format",
            },
        )

    def test_cli_help_is_available_without_error(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "maestro" / "runner.py"), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
