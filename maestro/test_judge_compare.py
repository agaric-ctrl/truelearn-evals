"""Tests for the Tier 3 judge-comparison CLI (maestro/judge/compare_gold_suites.py). Offline only -
this file never invokes a real judge; it only builds hand-written EvaluationResult-shaped JSON and
checks the comparison output, which is what compare_gold_suites.py itself does at runtime too.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "maestro" / "judge" / "compare_gold_suites.py"


def _result(framework: str, cases: list[dict]) -> dict:
    return {"framework": framework, "metric": "faithfulness_experimental_unvalidated", "cases": cases}


def _write(tmp: Path, name: str, data: dict) -> Path:
    path = tmp / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class CompareGoldSuitesCliTests(unittest.TestCase):
    def test_help_is_available(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())

    def test_requires_at_least_two_result_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "one.json", _result("maestro", [{"case_id": "a", "score": 1.0, "passed": True}]))
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("at least two", result.stderr.lower())

    def test_full_agreement_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            deepeval = _write(tmp_path, "deepeval.json", _result("maestro", [
                {"case_id": "grounded_anaphylaxis", "score": 1.0, "passed": True},
                {"case_id": "hallucinated_anaphylaxis_contradiction", "score": 0.5, "passed": False},
            ]))
            ragas = _write(tmp_path, "ragas.json", _result("maestro_ragas", [
                {"case_id": "grounded_anaphylaxis", "score": 0.95, "passed": True},
                {"case_id": "hallucinated_anaphylaxis_contradiction", "score": 0.3, "passed": False},
            ]))
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(deepeval), str(ragas)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["disagreement_count"], 0)
            self.assertEqual(report["agreement_count"], 2)
            self.assertEqual(sorted(report["frameworks"]), ["maestro", "maestro_ragas"])

    def test_disagreement_exits_nonzero_and_names_the_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            deepeval = _write(tmp_path, "deepeval.json", _result("maestro", [
                {"case_id": "grounded_anaphylaxis", "score": 1.0, "passed": True},
                {"case_id": "contested_case", "score": 0.95, "passed": True},
            ]))
            ragas = _write(tmp_path, "ragas.json", _result("maestro_ragas", [
                {"case_id": "grounded_anaphylaxis", "score": 0.9, "passed": True},
                {"case_id": "contested_case", "score": 0.4, "passed": False},
            ]))
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(deepeval), str(ragas)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertEqual(report["disagreement_count"], 1)
            self.assertIn("contested_case", result.stderr)

    def test_three_way_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = [
                _write(tmp_path, f"{name}.json", _result(name, [{"case_id": "c1", "score": 1.0, "passed": True}]))
                for name in ("maestro", "maestro_ragas", "promptfoo")
            ]
            result = subprocess.run(
                [sys.executable, str(SCRIPT), *[str(p) for p in paths]],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(sorted(report["frameworks"]), ["maestro", "maestro_ragas", "promptfoo"])


if __name__ == "__main__":
    unittest.main()
