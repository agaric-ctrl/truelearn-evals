"""CLI: turns real Maestro generation output into a GoldenExample-shaped candidate batch JSONL,
ready to feed straight into golden/generate_pool.py --batch - closing the gap that
maestro/examples/sample_golden_batch.jsonl's own _placeholder note names ("no real pipeline yet for
turning actual Maestro-generated questions into candidates like this one").

No live Payload API call exists yet (see payload_api.py) - input comes from a JSONL file of
{"payload": ..., "metadata": ...} raw records (produced however the real integration ends up
fetching them) or, for offline dry runs, --mock.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from maestro.golden.models import write_jsonl
from maestro.ingestion.candidates import ingest_candidate_batch, load_raw_candidate_record
from maestro.ingestion.payload_api import mock_fetch_raw_candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert Maestro generation payloads into a GoldenExample-shaped candidate batch JSONL.",
    )
    parser.add_argument("--in", dest="input_path", type=Path, default=None,
                         help="JSONL of {payload, metadata} raw records.")
    parser.add_argument("--mock", action="store_true",
                         help="Use the offline mock source instead of --in (no live Payload API call exists yet).")
    parser.add_argument("--out", type=Path, required=True,
                         help="Output path for the GoldenExample-shaped candidate batch JSONL.")
    args = parser.parse_args()

    if bool(args.input_path) == bool(args.mock):
        parser.error("exactly one of --in or --mock is required.")

    raw_records = (
        mock_fetch_raw_candidates() if args.mock
        else [
            json.loads(line)
            for line in args.input_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    )

    pairs = [load_raw_candidate_record(record) for record in raw_records]
    candidates, skipped = ingest_candidate_batch(pairs)

    write_jsonl(args.out, candidates)
    print(f"Wrote {len(candidates)} candidate(s) to {args.out}.")
    if skipped:
        print(f"Skipped {len(skipped)} record(s) that did not parse as a well-formed candidate: "
              f"{', '.join(skipped)}")

    return 1 if skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
