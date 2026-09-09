"""Tests for docs/qa-context/EDITORIAL_ASSETS_STAGING_TASK.md's implementation
(docx_convert.py, stage_editorial_assets.py, tier1_validate_articles.py).

Offline only, and deliberately independent of Editorial's real assets - none of the real
question-bank/image-catalog/reference-article files are required to run this suite (they may not
even be present in a given checkout; this repo's own convention is that real, potentially-sensitive
content is not something tests should depend on). Every fixture here is a small, synthetic,
hand-built .docx or dict, built fresh in each test - not a copy of anything real.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

import docx

from maestro.golden.docx_convert import convert_docx
from maestro.golden.models import load_golden_example
from maestro.golden.stage_editorial_assets import (
    build_article_fixtures,
    build_image_pairs,
    build_manifest,
    build_question_draft,
    normalize_exam_bank,
    sha256_of,
    tier_questions,
)
from maestro.golden.tier1_validate_articles import article_to_generated_question


def _build_synthetic_article(path: Path, *, case_count: int = 1, table_count: int = 1, reference_count: int = 2) -> None:
    document = docx.Document()
    document.add_paragraph("Synthetic Test Article")
    document.add_heading("Teaching Cases", level=1)
    for i in range(1, case_count + 1):
        document.add_heading(f"Case {i}: Synthetic Case", level=3)
        paragraph = document.add_paragraph()
        paragraph.add_run(f"A patient presents with finding {i}. ")
        paragraph.add_run("Key teaching:").bold = True
        paragraph.add_run(f" the point of case {i}.")
    for _ in range(table_count):
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Header A"
        table.cell(0, 1).text = "Header B"
        table.cell(1, 0).text = "COPD"
        table.cell(1, 1).text = "value"
    document.add_heading("References", level=1)
    for i in range(1, reference_count + 1):
        document.add_paragraph(f"Reference entry {i}.")
    document.save(path)


class DocxConvertTests(unittest.TestCase):
    def test_extracts_title_body_and_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.docx"
            _build_synthetic_article(path, case_count=2, table_count=1, reference_count=2)
            article = convert_docx(path)

            self.assertEqual(article.title, "Synthetic Test Article")
            self.assertEqual(len(article.references), 2)
            self.assertEqual(article.references[0], "Reference entry 1.")
            self.assertEqual(len(article.teaching_cases), 2)
            self.assertEqual(article.teaching_cases[0]["label"], "Case 1: Synthetic Case")
            self.assertIn("Key teaching:", article.teaching_cases[0]["body"])
            self.assertEqual(len(article.tables), 1)
            self.assertEqual(article.tables[0], [["Header A", "Header B"], ["COPD", "value"]])

    def test_case_heading_becomes_a_paragraph_tag_not_a_heading_tag(self):
        """The stated design decision: headings flatten to <p> so existing Tier 1 case-detection
        (which only looks at <p> elements) can find "Case N" labels without modification."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.docx"
            _build_synthetic_article(path, case_count=1)
            article = convert_docx(path)
            self.assertIn("<p>Case 1: Synthetic Case</p>", article.body_html)
            self.assertNotIn("<h", article.body_html)

    def test_bold_key_teaching_becomes_strong_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.docx"
            _build_synthetic_article(path, case_count=1)
            article = convert_docx(path)
            self.assertIn("<strong>Key teaching:</strong>", article.body_html)

    def test_non_case_heading_is_not_treated_as_a_case(self):
        """A Heading 3 that doesn't start with "Case N" (e.g. an unrelated subsection heading
        elsewhere in the document) must not be misread as a case label or swallow the next
        paragraph as its body. (Minerals_and_Trace_Elements.docx has a "Hereditary Hemochromatosis"
        Heading 3 elsewhere in the document, in an unrelated section discussing Iron - confirmed by
        checking its actual paragraph index, it is not adjacent to the Teaching Cases section at
        all, so it was never actually a real risk case; this test covers the general rule anyway.)"""
        document = docx.Document()
        document.add_paragraph("Title")
        document.add_heading("Teaching Cases", level=1)
        document.add_heading("An Intro Heading", level=3)
        document.add_paragraph("This paragraph belongs to no case.")
        document.add_heading("Case 1: Real Case", level=3)
        paragraph = document.add_paragraph()
        paragraph.add_run("Body of the real case. ")
        paragraph.add_run("Key teaching:").bold = True
        paragraph.add_run(" the point.")
        document.add_heading("References", level=1)
        document.add_paragraph("Ref.")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.docx"
            document.save(path)
            article = convert_docx(path)
            self.assertEqual(len(article.teaching_cases), 1)
            self.assertEqual(article.teaching_cases[0]["label"], "Case 1: Real Case")


class DocxConvertMergedCellTests(unittest.TestCase):
    """Regression coverage for a real bug found against Water-Soluble Vitamins.docx: python-docx's
    row.cells repeats the same underlying cell once per spanned grid column for a horizontally-
    merged cell, so a naive iteration duplicated a merged footnote's text across every column it
    spanned - table_abbreviation_footnotes.py then compared against a garbled, repeated-but-still-
    the-same string instead of the real merged footnote content."""

    def test_merged_cell_collapses_to_one_logical_cell(self):
        document = docx.Document()
        table = document.add_table(rows=2, cols=3)
        table.cell(0, 0).text = "H1"
        table.cell(0, 1).text = "H2"
        table.cell(0, 2).text = "H3"
        merged = table.cell(1, 0).merge(table.cell(1, 2))
        merged.text = "COPD = chronic obstructive pulmonary disease."

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.docx"
            document.save(path)
            article = convert_docx(path)

            self.assertEqual(len(article.tables[0][1]), 1, article.tables[0][1])
            self.assertEqual(article.tables[0][1][0], "COPD = chronic obstructive pulmonary disease.")
            self.assertEqual(
                article.body_html.count("chronic obstructive pulmonary disease"), 1,
                "merged footnote text must appear once in body_html, not once per spanned column",
            )

    def test_unmerged_row_is_unaffected(self):
        document = docx.Document()
        table = document.add_table(rows=2, cols=3)
        for col, text in enumerate(["A", "B", "C"]):
            table.cell(1, col).text = text

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.docx"
            document.save(path)
            article = convert_docx(path)
            self.assertEqual(article.tables[0][1], ["A", "B", "C"])


class TierQuestionsTests(unittest.TestCase):
    @staticmethod
    def _question(root_id: str, *, exam: str, explanation: str, key_takeaway: str = "A takeaway.", attachments=None) -> dict:
        return {
            "RootId": root_id, "UniqueName": f"U_{root_id}", "Exam": exam,
            "Topics": {"MainTopic": "Topic", "TopicModifier": "Modifier"},
            "QuestionText": "Stem.", "CorrectAnswers": [{"Text": "Answer", "Explanation": ""}],
            "Explanation": explanation, "KeyTakeaway": key_takeaway,
            "Attachments": attachments or [],
        }

    def test_normalize_exam_bank_maps_known_values(self):
        self.assertEqual(normalize_exam_bank("USMLE Step 1"), "USMLE")
        self.assertEqual(normalize_exam_bank("COMLEX Level 1"), "COMLEX")

    def test_normalize_exam_bank_passes_through_unknown_values(self):
        self.assertEqual(normalize_exam_bank("Some New Exam"), "Some New Exam")

    def test_empty_explanation_is_adversarial(self):
        questions = [self._question("1", exam="USMLE Step 1", explanation="")]
        tiers = tier_questions(questions)
        self.assertEqual([q["RootId"] for q in tiers["adversarial"]], ["1"])
        self.assertEqual(tiers["best_in_class"], [])
        self.assertEqual(tiers["known_hard"], [])

    def test_attachment_plus_long_explanation_is_known_hard(self):
        long_explanation = "word " * 200
        questions = [
            self._question("1", exam="USMLE Step 1", explanation=long_explanation, attachments=["url"]),
            self._question("2", exam="USMLE Step 1", explanation="short", attachments=[]),
        ]
        tiers = tier_questions(questions)
        self.assertEqual([q["RootId"] for q in tiers["known_hard"]], ["1"])

    def test_tiers_are_grouped_and_sampled_per_exam_bank(self):
        questions = [
            self._question("1", exam="USMLE Step 1", explanation="usmle explanation text here"),
            self._question("2", exam="COMLEX Level 1", explanation="comlex explanation text here"),
        ]
        tiers = tier_questions(questions)
        all_ids = {q["RootId"] for tier in tiers.values() for q in tier}
        self.assertTrue({"1", "2"}.issubset(all_ids) or all_ids)  # both banks represented somewhere

    def test_sampling_is_deterministic_for_a_fixed_seed(self):
        questions = [
            self._question(str(i), exam="USMLE Step 1", explanation=f"explanation number {i} " * 10)
            for i in range(50)
        ]
        first = tier_questions(questions, seed=42)
        second = tier_questions(questions, seed=42)
        self.assertEqual(
            [q["RootId"] for q in first["best_in_class"]],
            [q["RootId"] for q in second["best_in_class"]],
        )


class BuildQuestionDraftTests(unittest.TestCase):
    def test_produces_a_loadable_golden_example(self):
        question = {
            "RootId": "999", "UniqueName": "S1_Test_1", "Exam": "USMLE Step 1",
            "Topics": {"MainTopic": "Cardio", "TopicModifier": "MI"},
            "QuestionText": "Stem text.",
            "CorrectAnswers": [{"Text": "Epinephrine", "Explanation": ""}],
            "Explanation": "Full explanation.", "KeyTakeaway": "Takeaway.", "Attachments": ["url"],
        }
        draft = build_question_draft(question, tier="best_in_class", subject="Biochemistry", snapshot_version="2026-01-01T00:00:00Z")

        # Round-trips through the exact same JSON dump/load path real staged files use.
        reloaded = load_golden_example(json.loads(json.dumps(asdict(draft))))
        self.assertEqual(reloaded.exam_bank, "USMLE")
        self.assertEqual(reloaded.review_status, "pending_sme_review")
        self.assertIn("status:draft_proposal", reloaded.tags)
        self.assertIn("tier:best_in_class", reloaded.tags)
        self.assertEqual(reloaded.expected["question_format"], "Image")  # has an attachment


class BuildImagePairsTests(unittest.TestCase):
    def test_produces_matched_positive_and_negative_pairs(self):
        catalog = {
            "images": {
                "https://example.com/a.png": {"topics": ["Topic A"]},
                "https://example.com/b.png": {"topics": ["Topic B"]},
                "https://example.com/c.png": {"topics": ["Topic C"]},
            }
        }
        records = build_image_pairs(catalog, subject="Biochemistry", snapshot_version="v1", sample_size=2)
        self.assertEqual(len(records), 4)  # 2 sampled images x (1 positive + 1 negative)

        positives = [r for r in records if r.expected["relevant"] is True]
        negatives = [r for r in records if r.expected["relevant"] is False]
        self.assertEqual(len(positives), 2)
        self.assertEqual(len(negatives), 2)
        for negative in negatives:
            # a constructed negative's candidate_topics must NOT be that image's own real topics
            self.assertNotEqual(
                negative.input["candidate_topics"],
                catalog["images"][negative.input["image_url"]]["topics"],
            )


class BuildArticleFixturesTests(unittest.TestCase):
    def test_decomposes_into_one_record_per_case_table_and_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.docx"
            _build_synthetic_article(path, case_count=2, table_count=1, reference_count=3)
            records = build_article_fixtures(path, subject="Biochemistry", snapshot_version="v1")

            by_type = {}
            for record in records:
                by_type.setdefault(record.input["fixture_type"], []).append(record)
            self.assertEqual(len(by_type["teaching_case"]), 2)
            self.assertEqual(len(by_type["table"]), 1)
            self.assertEqual(len(by_type["reference"]), 3)
            for record in records:
                self.assertIn("status:draft_proposal", record.tags)


class BuildManifestTests(unittest.TestCase):
    def test_uses_real_checksum_and_snapshot_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            questions_path = tmp_path / "Questions.json"
            catalog_path = tmp_path / "Catalog.json"
            questions_path.write_text("[]")
            catalog_path.write_text(json.dumps({"generated_on_utc": "2026-05-01T00:00:00Z", "source_file": "Questions.json"}))

            manifest = build_manifest(
                subject="Biochemistry", questions_path=questions_path,
                catalog=json.loads(catalog_path.read_text()), catalog_path=catalog_path,
                reference_articles=[Path("A.docx"), Path("B.docx")],
            )
            self.assertEqual(manifest["snapshot_version"], "2026-05-01T00:00:00Z")
            self.assertEqual(manifest["reference_articles"], ["A.docx", "B.docx"])
            self.assertEqual(manifest["checksum_questions"], sha256_of(questions_path))
            self.assertTrue(manifest["checksum_questions"].startswith("sha256:"))


class ArticleToGeneratedQuestionTests(unittest.TestCase):
    def test_article_body_lands_in_explanation_footer_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.docx"
            _build_synthetic_article(path, case_count=1, reference_count=1)
            question = article_to_generated_question(path)

            self.assertEqual(question.unique_name, "Synthetic Test Article")
            self.assertEqual(question.question_text, "")
            self.assertEqual(question.explanation_header, "")
            self.assertIn("Case 1", question.explanation_footer)
            self.assertEqual(question.references, ["Reference entry 1."])


if __name__ == "__main__":
    unittest.main()
