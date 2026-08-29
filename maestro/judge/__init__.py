"""Tier 3: LLM-judge faithfulness scoring for Maestro-generated content.

EXPERIMENTAL. Validated only against maestro/judge/fixtures/synthetic_cases.json (hand-crafted by
an engineer, NOT real SME-graded data). Its agreement with real SME judgment has not been measured.
Not imported by generate_pool.py, import_pool.py, runner.py, or any CI gate. Off by default - run
maestro/judge/run_gold_suite.py by hand.
"""
