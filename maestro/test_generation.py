"""Tests for the Maestro generation payload model and revision-loop checks.

Everything here is offline - no live model calls, no live URL fetches. What's proven is that the
code correctly handles both hypotheticals about the unconfirmed real payload shape (e.g. whether a
history[] entry nests question fields flatly), not which hypothesis is actually true - that can
only be confirmed against real Maestro data.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from maestro.check_result import Status
from maestro.generation.checks import check_generation_payload
from maestro.generation.payload import (
    GenerationPayload,
    GenerationRecord,
    ReferenceResult,
    ReferencesPayload,
    history_entry_as_generated_question,
    load_generation_payload,
    load_reference_result,
    load_references_payload,
)
from maestro.models import EvalConfig

ROOT = Path(__file__).resolve().parents[1]


def _generated_question_dict(unique_name: str, **overrides) -> dict:
    base = {
        "unique_name": unique_name,
        "question_text": "<p>Stem.</p>",
        "explanation_header": "<p>Answer.</p>",
        "explanation_footer": "<p>Footer.</p>",
        "main_topic": "Cardiology",
        "modifier": "Adult",
        "question_type": "single question",
        "question_format": "Text",
    }
    base.update(overrides)
    return base


class ReferencesPayloadLoaderTests(unittest.TestCase):
    def test_reference_result_text_defaults_to_none_when_absent(self):
        result = load_reference_result({"url": "https://example.com", "score": 0.9})
        self.assertIsNone(result.text)

    def test_reference_result_text_populated_when_present(self):
        result = load_reference_result({"url": "https://example.com", "score": 0.9, "text": "excerpt"})
        self.assertEqual(result.text, "excerpt")

    def test_references_payload_round_trip(self):
        payload = load_references_payload({
            "query": "anaphylaxis treatment",
            "results": [{"url": "https://a.com", "score": 0.8}, {"url": "https://b.com", "score": 0.5}],
        })
        self.assertEqual(payload.query, "anaphylaxis treatment")
        self.assertEqual(len(payload.results), 2)
        self.assertEqual(payload.results[0].url, "https://a.com")


class GenerationPayloadLoaderTests(unittest.TestCase):
    def test_empty_payload_defaults(self):
        payload = load_generation_payload({})
        self.assertEqual(payload.history, [])
        self.assertEqual(payload.chat_history, [])
        self.assertEqual(payload.raw, {})

    def test_raw_preserved_verbatim(self):
        data = {"history": [], "chat_history": [], "some_future_field": 42}
        payload = load_generation_payload(data)
        self.assertEqual(payload.raw, data)

    def test_history_entries_carry_their_own_references(self):
        data = {
            "history": [
                {"references": {"query": "q1", "results": []}, "unique_name": "Q1"},
                {"references": {"query": "q2", "results": []}, "unique_name": "Q2"},
            ],
        }
        payload = load_generation_payload(data)
        self.assertEqual(len(payload.history), 2)
        self.assertEqual(payload.history[0].references.query, "q1")
        self.assertEqual(payload.history[1].references.query, "q2")


class HistoryEntryAsGeneratedQuestionTests(unittest.TestCase):
    def test_well_formed_flat_entry_parses(self):
        record = GenerationRecord(raw=_generated_question_dict("Test_001"))
        parsed = history_entry_as_generated_question(record)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.unique_name, "Test_001")

    def test_references_key_never_assigned_from_raw(self):
        """Locks in the exclusion decision: a raw entry that nests question fields alongside a
        ReferencesPayload-shaped "references" key must never let that dict flow into
        GeneratedQuestion.references (which every Tier 1 check assumes is list[str])."""
        raw = _generated_question_dict("Test_002")
        raw["references"] = {"query": "some query", "results": [{"url": "https://x.com"}]}
        record = GenerationRecord(raw=raw)
        parsed = history_entry_as_generated_question(record)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.references, [])

    def test_completely_unrelated_shape_returns_none(self):
        """Zero keys overlapping GeneratedQuestion's fields means this doesn't look like a
        GeneratedQuestion at all - must return None, not an all-empty-but-valid object."""
        record = GenerationRecord(raw={"totally_different_field": "value", "another": 1})
        self.assertIsNone(history_entry_as_generated_question(record))

    def test_non_dict_raw_does_not_raise(self):
        record = GenerationRecord(raw="not a dict")  # type: ignore[arg-type]
        self.assertIsNone(history_entry_as_generated_question(record))


class CheckGenerationPayloadTests(unittest.TestCase):
    def test_empty_history_fails_not_skips(self):
        report = check_generation_payload(GenerationPayload(), EvalConfig())
        head_result = next(r for r in report.results if r.check_name == "history_head_present")
        self.assertEqual(head_result.status, Status.FAIL)

    def test_broken_middle_revision_is_located_and_flagged(self):
        good_1 = _generated_question_dict("Q1")
        broken_2 = _generated_question_dict("Q2", question_text="")  # fails required_fields_present
        good_3 = _generated_question_dict("Q3")

        payload = GenerationPayload(history=[
            GenerationRecord(raw=good_1),
            GenerationRecord(raw=broken_2),
            GenerationRecord(raw=good_3),
        ])
        report = check_generation_payload(payload, EvalConfig())

        broken_failures = [r for r in report.results if r.status == Status.FAIL and r.field_name and r.field_name.startswith("history[1]")]
        self.assertTrue(broken_failures, "expected at least one FAIL located at history[1].*")

        other_failures = [r for r in report.results if r.status == Status.FAIL and r.field_name and not r.field_name.startswith("history[1]")]
        self.assertEqual(other_failures, [], f"unexpected FAILs outside history[1]: {other_failures}")

    def test_report_unique_name_matches_history_head(self):
        payload = GenerationPayload(history=[GenerationRecord(raw=_generated_question_dict("Head_Q"))])
        report = check_generation_payload(payload, EvalConfig())
        self.assertEqual(report.unique_name, "Head_Q")

    def test_chat_history_alignment_always_skipped(self):
        payload = GenerationPayload(
            history=[GenerationRecord(raw=_generated_question_dict("Q1"))],
            chat_history=[{"instruction": "a"}, {"instruction": "b"}, {"instruction": "c"}],  # mismatched length
        )
        report = check_generation_payload(payload, EvalConfig())
        alignment_result = next(r for r in report.results if r.check_name == "chat_history_alignment")
        self.assertEqual(alignment_result.status, Status.SKIPPED)


class RunnerCliSmokeTests(unittest.TestCase):
    def test_help_is_available(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "maestro" / "generation" / "checks.py"), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
