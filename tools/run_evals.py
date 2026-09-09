"""Run the Python faithfulness demos and collect normalized results."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run_demo(
    name: str, script: Path, python: str, timeout_seconds: float, attempts: int
) -> dict[str, Any]:
    if timeout_seconds <= 0 or attempts < 1:
        raise ValueError("timeout_seconds must be positive and attempts must be positive")
    for attempt in range(attempts):
        try:
            completed = subprocess.run(
                [python, str(script), "--json"],
                cwd=script.parent,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            if attempt == attempts - 1:
                raise RuntimeError(f"{name} exceeded {timeout_seconds} seconds")
            continue
        if completed.returncode == 0:
            break
        if attempt == attempts - 1:
            raise RuntimeError(
                f"{name} failed with exit code {completed.returncode}:\n"
                f"{completed.stderr.strip()}"
            )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{name} did not emit valid JSON:\n{completed.stdout}"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=900,
        help="Timeout for each framework subprocess.",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=2,
        help="Maximum attempts for each framework subprocess.",
    )
    parser.add_argument(
        "--deepeval-python",
        default=sys.executable,
        help="Python executable for the DeepEval environment.",
    )
    parser.add_argument(
        "--ragas-python",
        default=sys.executable,
        help="Python executable for the RAGAS environment.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "python-results.json",
        help="Path for the combined normalized result file.",
    )
    args = parser.parse_args()

    results = [
        run_demo(
            "DeepEval",
            ROOT / "evaluations" / "faithfulness" / "deepeval" / "faithfulness_demo.py",
            args.deepeval_python, args.timeout_seconds, args.attempts,
        ),
        run_demo(
            "RAGAS",
            ROOT / "evaluations" / "faithfulness" / "ragas" / "ragas_faithfulness.py",
            args.ragas_python, args.timeout_seconds, args.attempts,
        ),
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
