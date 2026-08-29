"""Candidate-ingestion seam: converts real Maestro generation output into the harness's
GeneratedQuestion / GoldenExample-shaped candidate-batch input (see
maestro/examples/sample_golden_batch.jsonl, whose own _placeholder note names this exact gap).

Built up to, and deliberately stopping at, the [UNCONFIRMED] Payload API boundary - see
payload_api.py. Maestro's real endpoint/auth contract is not confirmed, so no live HTTP call is
made anywhere in this package. mock_fetch_raw_candidates() is the offline substitute used by tests
and --mock dry runs.
"""
