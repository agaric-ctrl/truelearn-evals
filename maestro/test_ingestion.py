"""Tests for the candidate-ingestion seam (maestro/ingestion/). Offline only - fetch_raw_candidates()
is proven to raise rather than silently succeed; no live Payload API call is made or possible.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from maestro.generation.payload import GenerationPayload, GenerationRecord
from maestro.golden.generate_pool import build_review_pool
from maestro.golden.models import read_jsonl
from maestro.ingestion.candidates import (
    CandidateMetadata,
    generation_payload_to_candidate,
    ingest_candidate_batch,
    load_raw_candidate_record,
)
from maestro.ingestion.payload_api import (
    PayloadApiConfig,
    fetch_raw_candidates,
    mock_fetch_raw_candidates,
)

ROOT = Path(__file__).resolve().parents[1]


def _question_dict(unique_name: str, **overrides) -> dict:
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


class GenerationPayloadToCandidateTests(unittest.TestCase):
    def test_well_formed_history_head_converts(self):
        payload = GenerationPayload(history=[GenerationRecord(raw=_question_dict("Q1"))])
        metadata = CandidateMetadata(
            example_id="ex-1", exam_bank="USMLE", source_type="topic",
            input_data={"topic": "Something"}, ac_ref="AC-1", tags=["a"],
        )
        candidate = generation_payload_to_candidate(payload, metadata)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.example_id, "ex-1")
        self.assertEqual(candidate.exam_bank, "USMLE")
        self.assertEqual(candidate.source_type, "topic")
        self.assertEqual(candidate.question_type, "single question")
        self.assertEqual(candidate.expected["unique_name"], "Q1")
        self.assertEqual(candidate.input, {"topic": "Something"})
        self.assertEqual(candidate.ac_ref, "AC-1")
        self.assertEqual(candidate.tags, ["a"])

    def test_empty_history_returns_none(self):
        self.assertIsNone(generation_payload_to_candidate(GenerationPayload(), CandidateMetadata()))

    def test_unparseable_history_head_returns_none(self):
        payload = GenerationPayload(history=[GenerationRecord(raw={"nothing": "matches"})])
        self.assertIsNone(generation_payload_to_candidate(payload, CandidateMetadata()))


class IngestCandidateBatchTests(unittest.TestCase):
    def test_mixed_batch_splits_candidates_and_skipped(self):
        good = GenerationPayload(history=[GenerationRecord(raw=_question_dict("Good"))])
        bad = GenerationPayload()  # empty history
        pairs = [
            (good, CandidateMetadata(example_id="ex-good", exam_bank="USMLE", source_type="topic")),
            (bad, CandidateMetadata(example_id="ex-bad", exam_bank="USMLE", source_type="topic")),
        ]
        candidates, skipped = ingest_candidate_batch(pairs)
        self.assertEqual([c.example_id for c in candidates], ["ex-good"])
        self.assertEqual(skipped, ["ex-bad"])

    def test_load_raw_candidate_record_round_trips(self):
        raw = {
            "payload": {"history": [_question_dict("RT1")], "chat_history": []},
            "metadata": {"example_id": "ex-rt", "exam_bank": "COMLEX", "source_type": "question_edit"},
        }
        payload, metadata = load_raw_candidate_record(raw)
        self.assertEqual(payload.history[0].raw["unique_name"], "RT1")
        self.assertEqual(metadata.example_id, "ex-rt")


class PayloadApiBoundaryTests(unittest.TestCase):
    def test_config_defaults_are_unconfirmed(self):
        config = PayloadApiConfig()
        self.assertIsNone(config.base_url)
        self.assertIsNone(config.auth_token_env)

    def test_fetch_raises_not_implemented_even_with_config_set(self):
        """Proves this never silently attempts a guessed HTTP call even once a caller has filled in
        a base_url - the real endpoint/auth/pagination contract is still unconfirmed."""
        config = PayloadApiConfig(base_url="https://example.com/api", auth_token_env="MAESTRO_TOKEN")
        with self.assertRaises(NotImplementedError):
            fetch_raw_candidates(config)

    def test_mock_source_returns_candidate_shaped_records(self):
        records = mock_fetch_raw_candidates()
        self.assertTrue(records)
        for record in records:
            self.assertIn("payload", record)
            self.assertIn("metadata", record)

    def test_mock_source_round_trips_through_the_full_pipeline(self):
        pairs = [load_raw_candidate_record(record) for record in mock_fetch_raw_candidates()]
        candidates, skipped = ingest_candidate_batch(pairs)
        self.assertEqual(skipped, [])
        self.assertTrue(candidates)


class IngestBatchCliTests(unittest.TestCase):
    def test_help_is_available(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "maestro" / "ingestion" / "ingest_batch.py"), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())

    def test_mock_dry_run_produces_a_batch_generate_pool_can_consume(self):
        """Proves the seam actually connects to Tier 2, not just that it produces JSON that looks
        right in isolation."""
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "batch.jsonl"
            result = subprocess.run(
                [sys.executable, str(ROOT / "maestro" / "ingestion" / "ingest_batch.py"),
                 "--mock", "--out", str(out_path)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            candidates = read_jsonl(out_path)
            self.assertTrue(candidates)
            _workbook, mapping = build_review_pool(candidates, seed=1)
            self.assertEqual(len(mapping["rows"]), len(candidates))

    def test_requires_exactly_one_of_in_or_mock(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "batch.jsonl"
            result = subprocess.run(
                [sys.executable, str(ROOT / "maestro" / "ingestion" / "ingest_batch.py"),
                 "--out", str(out_path)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
