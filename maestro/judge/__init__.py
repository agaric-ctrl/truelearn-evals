"""Tier 3: LLM-judge scoring for Maestro-generated content - faithfulness (3 independent
implementations: deepeval, RAGAS, Promptfoo), non-contradiction, and source-coverage.

EXPERIMENTAL, all five. Each is validated only against its own hand-crafted synthetic fixtures
(maestro/judge/fixtures/*.json), NOT real SME-graded data. Their agreement with real SME judgment
has not been measured. Not imported by generate_pool.py, import_pool.py, runner.py, or any CI gate.
Off by default - run any maestro/judge/run_gold_suite*.py script by hand.
"""
