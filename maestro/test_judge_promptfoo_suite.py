"""Consistency check for judge/promptfoo/synthetic_cases_suite.yaml - a third, rubric-based Tier 3
judge whose test cases are hand-transcribed from judge/fixtures/synthetic_cases.json (the same
fixture run_gold_suite.py/run_gold_suite_ragas.py use).

This cannot verify the config actually scores correctly under Promptfoo - that requires Node and a
live model call, and is deliberately not part of this offline suite (same as every other live-model
path in this repo). What it CAN verify, without running Node at all: the transcription is exact (no
copy/paste drift between the YAML and the JSON fixture) and the config has the structural shape a
real Promptfoo rubric needs - most importantly, that {{source}} is actually injected into the
rubric text. The root README documents exactly this failure mode: an earlier rubric never injected
{{source}}, so the judge couldn't see the source material at all and silently failed to grade
groundedness. This test exists so that mistake can't recur here undetected.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

from maestro.judge.shared import build_actual_output

ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "maestro" / "judge" / "promptfoo" / "synthetic_cases_suite.yaml"
FIXTURE_PATH = ROOT / "maestro" / "judge" / "fixtures" / "synthetic_cases.json"


def _load_suite() -> dict:
    return yaml.safe_load(SUITE_PATH.read_text(encoding="utf-8"))


def _load_fixture() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class SuiteStructureTests(unittest.TestCase):
    def setUp(self):
        self.suite = _load_suite()

    def test_uses_echo_provider(self):
        """Confirms no model generates - only the rubric judge makes a call, isolating the judge
        under test exactly like reference/promptfoo/01_faithfulness_pass_fail.yaml does."""
        self.assertEqual(self.suite["providers"], [{"id": "echo"}])

    def test_rubric_assertion_is_llm_rubric(self):
        assertions = self.suite["defaultTest"]["assert"]
        self.assertEqual(len(assertions), 1)
        self.assertEqual(assertions[0]["type"], "llm-rubric")

    def test_source_variable_is_actually_injected_into_the_rubric(self):
        """Regression test for the exact documented pitfall (root README, "Framework comparison"
        section): a rubric that never injects {{source}} silently can't check groundedness at all."""
        rubric_text = self.suite["defaultTest"]["assert"][0]["value"]
        self.assertIn("{{source}}", rubric_text)

    def test_prompt_references_answer_under_test(self):
        self.assertIn("{{answer_under_test}}", self.suite["prompts"])


class SuiteMatchesFixtureTests(unittest.TestCase):
    def setUp(self):
        self.suite = _load_suite()
        self.fixture = _load_fixture()

    def test_every_fixture_case_appears_exactly_once(self):
        suite_ids = [test["description"] for test in self.suite["tests"]]
        fixture_ids = [case["case_id"] for case in self.fixture]
        self.assertEqual(sorted(suite_ids), sorted(fixture_ids))
        self.assertEqual(len(suite_ids), len(set(suite_ids)), "duplicate case_id in the YAML suite")

    def test_source_and_answer_exactly_match_the_fixture(self):
        """The single most likely real mistake in a hand-transcribed file: this proves it isn't
        one, without needing Node/Promptfoo installed anywhere."""
        tests_by_id = {test["description"]: test["vars"] for test in self.suite["tests"]}
        for case in self.fixture:
            case_id = case["case_id"]
            self.assertIn(case_id, tests_by_id, f"{case_id} missing from the YAML suite")
            suite_vars = tests_by_id[case_id]

            self.assertEqual(len(case["source"]), 1,
                              f"{case_id}: fixture has >1 source string, YAML only carries one")
            self.assertEqual(suite_vars["source"], case["source"][0])

            expected_answer = build_actual_output(**case["generated"])
            self.assertEqual(suite_vars["answer_under_test"], expected_answer)


if __name__ == "__main__":
    unittest.main()
