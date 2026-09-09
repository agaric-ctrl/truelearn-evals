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
from maestro.checks.arrow_style import arrow_style
from maestro.checks.case_numbering import case_numbering
from maestro.checks.density_redundancy import density_redundancy
from maestro.checks.field_constraints import field_constraints
from maestro.checks.html_well_formed import html_well_formed
from maestro.checks.markdown_structural_compatibility import markdown_structural_compatibility
from maestro.checks.readability_check import readability
from maestro.checks.references_format import references_format
from maestro.checks.required_fields_present import required_fields_present
from maestro.checks.table_abbreviation_footnotes import table_abbreviation_footnotes
from maestro.checks.tables_no_duplicates import tables_no_duplicates
from maestro.checks.tables_placement_valid import tables_placement_valid
from maestro.checks.teaching_case_standard import teaching_case_standard
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
# references_format.py - originally a Skip-only stub (style_pattern sub-check only); the Tier 1
# checks task filled in reference_count, reverse_chronological_order, citation_type_caps, and
# excluded_sources as new sub-checks alongside it. Behavior change worth calling out: an empty
# references list used to be a blanket PASS (there was no real rule yet); now it correctly FAILs
# reference_count (0 is outside the required 3-5), since that's now a real, stated rule.
# ---------------------------------------------------------------------------

class ReferencesFormatTests(unittest.TestCase):
    @staticmethod
    def _question(references: list[str]) -> GeneratedQuestion:
        return GeneratedQuestion(references=references)

    def test_count_in_range_passes(self):
        question = self._question([
            "Smith J. Journal A. 2022.", "Doe R. Journal B. 2021.", "Lee K. Journal C. 2020.",
        ])
        result = _single(references_format(question, EvalConfig()), sub_check="reference_count")
        self.assertEqual(result.status, Status.PASS)

    def test_too_few_references_fails(self):
        question = self._question(["Smith J. Journal A. 2022."])
        result = _single(references_format(question, EvalConfig()), sub_check="reference_count")
        self.assertEqual(result.status, Status.FAIL)

    def test_too_many_references_fails(self):
        question = self._question([f"Author {i}. Journal. 202{i}." for i in range(6)])
        result = _single(references_format(question, EvalConfig()), sub_check="reference_count")
        self.assertEqual(result.status, Status.FAIL)

    def test_reverse_chronological_order_passes(self):
        question = self._question([
            "Smith J. Journal A. 2022.", "Doe R. Journal B. 2021.", "Lee K. Journal C. 2020.",
        ])
        result = _single(
            references_format(question, EvalConfig()), sub_check="reverse_chronological_order",
        )
        self.assertEqual(result.status, Status.PASS)

    def test_out_of_order_years_fails(self):
        question = self._question([
            "Smith J. Journal A. 2020.", "Doe R. Journal B. 2022.", "Lee K. Journal C. 2021.",
        ])
        result = _single(
            references_format(question, EvalConfig()), sub_check="reverse_chronological_order",
        )
        self.assertEqual(result.status, Status.FAIL)

    def test_ordering_skipped_with_fewer_than_two_dated_references(self):
        question = self._question(["No year here.", "Also no year."])
        result = _single(
            references_format(question, EvalConfig()), sub_check="reverse_chronological_order",
        )
        self.assertEqual(result.status, Status.SKIPPED)

    def test_citation_type_caps_skipped_when_unconfigured(self):
        question = self._question(["Smith J. Journal A. 2022."])
        result = _single(references_format(question, EvalConfig()), sub_check="citation_type_caps")
        self.assertEqual(result.status, Status.SKIPPED)

    def test_citation_type_cap_exceeded_fails(self):
        config = EvalConfig(
            reference_citation_type_patterns={"guideline": r"Guideline"},
            max_per_citation_type={"guideline": 1},
        )
        question = self._question([
            "ACC/AHA Guideline 2022.", "ESC Guideline 2021.", "Smith J. Journal. 2020.",
        ])
        result = _single(references_format(question, config), sub_check="citation_type_caps")
        self.assertEqual(result.status, Status.FAIL)

    def test_citation_type_cap_within_limit_passes(self):
        config = EvalConfig(
            reference_citation_type_patterns={"guideline": r"Guideline"},
            max_per_citation_type={"guideline": 2},
        )
        question = self._question(["ACC/AHA Guideline 2022.", "Smith J. Journal. 2020."])
        result = _single(references_format(question, config), sub_check="citation_type_caps")
        self.assertEqual(result.status, Status.PASS)

    def test_excluded_sources_skipped_when_unconfigured(self):
        question = self._question(["Wikipedia. Some topic. 2022."])
        result = _single(references_format(question, EvalConfig()), sub_check="excluded_sources")
        self.assertEqual(result.status, Status.SKIPPED)

    def test_excluded_source_found_fails(self):
        config = EvalConfig(excluded_reference_sources={"Wikipedia"})
        question = self._question(["Wikipedia. Some topic. 2022.", "Smith J. Journal. 2020."])
        result = _single(references_format(question, config), sub_check="excluded_sources")
        self.assertEqual(result.status, Status.FAIL)

    def test_excluded_source_absent_passes(self):
        config = EvalConfig(excluded_reference_sources={"Wikipedia"})
        question = self._question(["Smith J. Journal. 2020."])
        result = _single(references_format(question, config), sub_check="excluded_sources")
        self.assertEqual(result.status, Status.PASS)

    def test_style_pattern_skipped_when_unset(self):
        question = self._question(["Smith et al., 2020"])
        result = _single(references_format(question, EvalConfig()), sub_check="style_pattern")
        self.assertEqual(result.status, Status.SKIPPED)

    def test_style_pattern_produces_no_rows_when_no_references(self):
        config = EvalConfig(reference_style_pattern=r"[A-Z][a-z]+ et al\., \d{4}")
        results = [
            result for result in references_format(self._question([]), config)
            if result.sub_check == "style_pattern"
        ]
        self.assertEqual(results, [])

    def test_each_reference_checked_independently_against_style_pattern(self):
        config = EvalConfig(reference_style_pattern=r"[A-Z][a-z]+ et al\., \d{4}")
        question = self._question(["Smith et al., 2020", "not styled correctly"])
        results = [
            result for result in references_format(question, config)
            if result.sub_check == "style_pattern"
        ]
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
                "table_abbreviation_footnotes", "teaching_case_standard", "case_numbering",
                "readability", "markdown_structural_compatibility", "density_redundancy",
                "arrow_style",
            },
        )

    def test_cli_help_is_available_without_error(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "maestro" / "runner.py"), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())


# ---------------------------------------------------------------------------
# table_abbreviation_footnotes.py - new (docs/qa-context/TIER1_CHECKS_TASK.md)
# ---------------------------------------------------------------------------

class TableAbbreviationFootnotesTests(unittest.TestCase):
    def test_no_tables_skipped(self):
        question = GeneratedQuestion(question_text="<p>No table here.</p>")
        results = table_abbreviation_footnotes(question, EvalConfig())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.SKIPPED)

    def test_abbreviation_defined_in_footnote_passes(self):
        question = GeneratedQuestion(explanation_footer=(
            "<table><tr><th>Test</th></tr><tr><td>COPD</td></tr>"
            "<tr><td>COPD = chronic obstructive pulmonary disease</td></tr></table>"
        ))
        result = _single(table_abbreviation_footnotes(question, EvalConfig()))
        self.assertEqual(result.status, Status.PASS)

    def test_abbreviation_missing_from_footnote_fails(self):
        question = GeneratedQuestion(explanation_footer=(
            "<table><tr><th>Test</th></tr><tr><td>COPD</td></tr>"
            "<tr><td>Unrelated footnote text</td></tr></table>"
        ))
        result = _single(table_abbreviation_footnotes(question, EvalConfig()))
        self.assertEqual(result.status, Status.FAIL)
        self.assertIn("COPD", result.message)

    def test_no_abbreviations_in_table_passes(self):
        question = GeneratedQuestion(explanation_footer="<table><tr><td>plain text</td></tr></table>")
        result = _single(table_abbreviation_footnotes(question, EvalConfig()))
        self.assertEqual(result.status, Status.PASS)

    # False-positive fixes named in the task doc - verified against the exact failure patterns
    # (chemical-formula fragments, letter+number labels), not just the plain "COPD" happy path.

    def test_chemical_formula_fragment_not_flagged_as_abbreviation(self):
        question = GeneratedQuestion(explanation_footer=(
            "<table><tr><td>CO2 level elevated</td></tr>"
            "<tr><td>No abbreviations defined here</td></tr></table>"
        ))
        result = _single(table_abbreviation_footnotes(question, EvalConfig()))
        self.assertEqual(result.status, Status.PASS, result.message)

    def test_letter_number_label_not_flagged_as_abbreviation(self):
        """e.g. "CD4 count" - a real medical letter+digit label, not an undefined abbreviation."""
        question = GeneratedQuestion(explanation_footer=(
            "<table><tr><td>CD4 count low</td></tr>"
            "<tr><td>No abbreviations defined here</td></tr></table>"
        ))
        result = _single(table_abbreviation_footnotes(question, EvalConfig()))
        self.assertEqual(result.status, Status.PASS, result.message)

    def test_allowlisted_abbreviation_not_flagged(self):
        config = EvalConfig(abbreviation_allowlist={"DNA"})
        question = GeneratedQuestion(explanation_footer=(
            "<table><tr><td>DNA test</td></tr><tr><td>No footnote needed</td></tr></table>"
        ))
        result = _single(table_abbreviation_footnotes(question, config))
        self.assertEqual(result.status, Status.PASS, result.message)


# ---------------------------------------------------------------------------
# teaching_case_standard.py - new (docs/qa-context/TIER1_CHECKS_TASK.md)
# ---------------------------------------------------------------------------

class TeachingCaseStandardTests(unittest.TestCase):
    def test_no_cases_skipped(self):
        question = GeneratedQuestion(question_text="<p>No case sections here.</p>")
        results = teaching_case_standard(question, EvalConfig())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.SKIPPED)

    def test_case_within_sentence_limit_and_inline_key_teaching_passes(self):
        question = GeneratedQuestion(explanation_footer=(
            "<p>Case 1: A patient presents with fever. "
            "<strong>Key teaching:</strong> Treat the underlying infection promptly.</p>"
        ))
        results = teaching_case_standard(question, EvalConfig())
        self.assertTrue(results)
        self.assertTrue(all(result.status == Status.PASS for result in results), results)

    def test_case_exceeding_sentence_limit_fails(self):
        question = GeneratedQuestion(explanation_footer=(
            "<p>Case 1: One. Two. Three. Four. "
            "<strong>Key teaching:</strong> Some point.</p>"
        ))
        result = _single(teaching_case_standard(question, EvalConfig()), sub_check="sentence_ceiling")
        self.assertEqual(result.status, Status.FAIL)

    def test_missing_key_teaching_fails(self):
        question = GeneratedQuestion(
            explanation_footer="<p>Case 1: A patient presents with fever.</p>",
        )
        result = _single(
            teaching_case_standard(question, EvalConfig()), sub_check="key_teaching_present",
        )
        self.assertEqual(result.status, Status.FAIL)

    def test_key_teaching_starting_its_own_paragraph_fails(self):
        question = GeneratedQuestion(explanation_footer=(
            "<p>Case 1: A patient presents with fever.</p>"
            "<p><strong>Key teaching:</strong> Treat promptly.</p>"
        ))
        result = _single(
            teaching_case_standard(question, EvalConfig()), sub_check="key_teaching_inline",
        )
        self.assertEqual(result.status, Status.FAIL)

    def test_key_teaching_not_bolded_counts_as_missing(self):
        question = GeneratedQuestion(explanation_footer=(
            "<p>Case 1: A patient presents with fever. Key teaching: treat promptly.</p>"
        ))
        result = _single(
            teaching_case_standard(question, EvalConfig()), sub_check="key_teaching_present",
        )
        self.assertEqual(result.status, Status.FAIL)


# ---------------------------------------------------------------------------
# case_numbering.py - new (docs/qa-context/TIER1_CHECKS_TASK.md)
# ---------------------------------------------------------------------------

class CaseNumberingTests(unittest.TestCase):
    def test_no_cases_skipped(self):
        question = GeneratedQuestion(question_text="<p>No cases here.</p>")
        results = case_numbering(question, EvalConfig())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Status.SKIPPED)

    def test_sequential_numbering_passes(self):
        question = GeneratedQuestion(explanation_footer=(
            "<p>Case 1: First.</p><p>Case 2: Second.</p><p>Case 3: Third.</p>"
        ))
        result = _single(case_numbering(question, EvalConfig()))
        self.assertEqual(result.status, Status.PASS)

    def test_gap_in_numbering_fails(self):
        question = GeneratedQuestion(
            explanation_footer="<p>Case 1: First.</p><p>Case 3: Third.</p>",
        )
        result = _single(case_numbering(question, EvalConfig()))
        self.assertEqual(result.status, Status.FAIL)

    def test_numbering_not_starting_at_one_fails(self):
        question = GeneratedQuestion(
            explanation_footer="<p>Case 2: Second.</p><p>Case 3: Third.</p>",
        )
        result = _single(case_numbering(question, EvalConfig()))
        self.assertEqual(result.status, Status.FAIL)

    def test_cases_combined_across_fields(self):
        question = GeneratedQuestion(
            explanation_header="<p>Case 1: First.</p>",
            explanation_footer="<p>Case 2: Second.</p>",
        )
        result = _single(case_numbering(question, EvalConfig()))
        self.assertEqual(result.status, Status.PASS)


# ---------------------------------------------------------------------------
# readability.py - new (docs/qa-context/TIER1_CHECKS_TASK.md). PLACEHOLDER threshold - see the
# module docstring. Long repeated-sentence fixtures below exist only to clear
# py-readability-metrics' 100-word minimum, not because the content is meaningful prose.
# ---------------------------------------------------------------------------

class ReadabilityTests(unittest.TestCase):
    _LONG_TEXT = "<p>" + ("This is a plain, simple sentence for testing purposes. " * 20) + "</p>"

    def test_empty_field_skipped(self):
        result = _single(readability(GeneratedQuestion(), EvalConfig()), field_name="question_text")
        self.assertEqual(result.status, Status.SKIPPED)

    def test_short_text_skipped_not_scored(self):
        question = GeneratedQuestion(question_text="<p>Too short to score.</p>")
        result = _single(readability(question, EvalConfig()), field_name="question_text")
        self.assertEqual(result.status, Status.SKIPPED)
        self.assertIn("Not enough text", result.message)

    def test_skipped_when_range_unconfigured_but_score_still_reported(self):
        question = GeneratedQuestion(question_text=self._LONG_TEXT)
        result = _single(readability(question, EvalConfig()), field_name="question_text")
        self.assertEqual(result.status, Status.SKIPPED)
        self.assertIn("flesch_kincaid_grade_level", result.details)

    def test_in_range_passes_when_configured(self):
        question = GeneratedQuestion(question_text=self._LONG_TEXT)
        config = EvalConfig(readability_grade_level_range=(0.0, 100.0))
        result = _single(readability(question, config), field_name="question_text")
        self.assertEqual(result.status, Status.PASS)

    def test_out_of_range_fails_when_configured(self):
        question = GeneratedQuestion(question_text=self._LONG_TEXT)
        config = EvalConfig(readability_grade_level_range=(-100.0, -50.0))
        result = _single(readability(question, config), field_name="question_text")
        self.assertEqual(result.status, Status.FAIL)


# ---------------------------------------------------------------------------
# markdown_structural_compatibility.py - new (docs/qa-context/TIER1_CHECKS_TASK.md)
# ---------------------------------------------------------------------------

class MarkdownStructuralCompatibilityTests(unittest.TestCase):
    def test_empty_field_skipped(self):
        result = _single(
            markdown_structural_compatibility(GeneratedQuestion(), EvalConfig()),
            field_name="question_text",
        )
        self.assertEqual(result.status, Status.SKIPPED)

    def test_clean_html_passes(self):
        question = GeneratedQuestion(question_text="<p>A patient presents with <strong>fever</strong>.</p>")
        result = _single(
            markdown_structural_compatibility(question, EvalConfig()), field_name="question_text",
        )
        self.assertEqual(result.status, Status.PASS)

    def test_html_tags_alone_do_not_false_positive(self):
        """Regression test for the false positive this check would otherwise have: pymarkdownlnt's
        MD033 (no inline HTML) fires on every field if run against raw HTML, since HTML is this
        field's confirmed, expected shape, not a defect. Stripping tags first (see this check's
        module docstring) is what avoids it - verified directly against a real MD033 false-positive
        found while building this check, not assumed."""
        question = GeneratedQuestion(explanation_header="<p>Header text.</p>")
        result = _single(
            markdown_structural_compatibility(question, EvalConfig()),
            field_name="explanation_header",
        )
        self.assertEqual(result.status, Status.PASS)

    def test_hard_tab_detected(self):
        question = GeneratedQuestion(question_text="Some text.\n\tTab-indented line.")
        results = [
            result for result in markdown_structural_compatibility(question, EvalConfig())
            if result.field_name == "question_text"
        ]
        self.assertTrue(any(result.status == Status.FAIL for result in results), results)

    def test_excess_blank_lines_detected(self):
        question = GeneratedQuestion(question_text="Para one.\n\n\n\nPara two.")
        results = [
            result for result in markdown_structural_compatibility(question, EvalConfig())
            if result.field_name == "question_text"
        ]
        self.assertTrue(any(result.status == Status.FAIL for result in results), results)


# ---------------------------------------------------------------------------
# density_redundancy.py - new (docs/qa-context/TIER1_CHECKS_TASK.md). PLACEHOLDER threshold - see
# the module docstring. Overlap ratios below were verified directly (not assumed) before being
# hardcoded into these fixtures.
# ---------------------------------------------------------------------------

class DensityRedundancyTests(unittest.TestCase):
    def test_fewer_than_two_sentences_skipped(self):
        question = GeneratedQuestion(question_text="<p>Just one sentence here.</p>")
        result = _single(density_redundancy(question, EvalConfig()), field_name="question_text")
        self.assertEqual(result.status, Status.SKIPPED)

    def test_skipped_when_threshold_unconfigured_but_pairs_still_reported(self):
        question = GeneratedQuestion(question_text=(
            "<p>The patient has a fever. The patient has a high fever today.</p>"
        ))
        result = _single(density_redundancy(question, EvalConfig()), field_name="question_text")
        self.assertEqual(result.status, Status.SKIPPED)
        self.assertIn("pairs", result.details)

    def test_highly_overlapping_sentences_fail_when_configured(self):
        question = GeneratedQuestion(question_text=(
            "<p>The patient has a high fever today. The patient has a high fever currently.</p>"
        ))
        config = EvalConfig(max_ngram_overlap_ratio=0.3)
        result = _single(density_redundancy(question, config), field_name="question_text")
        self.assertEqual(result.status, Status.FAIL)

    def test_distinct_sentences_pass_when_configured(self):
        question = GeneratedQuestion(question_text=(
            "<p>The patient has a fever. Blood pressure is elevated significantly today.</p>"
        ))
        config = EvalConfig(max_ngram_overlap_ratio=0.3)
        result = _single(density_redundancy(question, config), field_name="question_text")
        self.assertEqual(result.status, Status.PASS)


# ---------------------------------------------------------------------------
# arrow_style.py - new (docs/qa-context/TIER1_CHECKS_TASK.md)
# ---------------------------------------------------------------------------

class ArrowStyleTests(unittest.TestCase):
    def test_no_arrow_passes(self):
        question = GeneratedQuestion(question_text="<p>No typed arrow here.</p>")
        result = _single(arrow_style(question, EvalConfig()), field_name="question_text")
        self.assertEqual(result.status, Status.PASS)

    def test_typed_arrow_fails(self):
        question = GeneratedQuestion(question_text="<p>A -> B progression.</p>")
        result = _single(arrow_style(question, EvalConfig()), field_name="question_text")
        self.assertEqual(result.status, Status.FAIL)
        self.assertEqual(result.details["count"], 1)

    def test_real_arrow_character_passes(self):
        question = GeneratedQuestion(question_text="<p>A → B progression.</p>")
        result = _single(arrow_style(question, EvalConfig()), field_name="question_text")
        self.assertEqual(result.status, Status.PASS)


if __name__ == "__main__":
    unittest.main()
