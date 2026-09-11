"""Validate security-critical GitHub Actions workflow invariants offline."""

from __future__ import annotations

import argparse
from pathlib import Path

LIVE_WORKFLOW_NAMES = {"faithfulness-framework-evaluation.yml", "maestro-comparative-ab-report.yml"}


def validate_workflow(path: Path, *, live: bool) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors = []
    if live:
        required = (
            "workflow_dispatch:",
            "permissions:",
            "contents: read",
            "ANTHROPIC_API_KEY",
            "timeout-minutes: 15",
            "Require API key",
        )
        errors.extend(
            f"{path}: missing required safeguard {item!r}"
            for item in required
            if item not in text
        )
    elif path.stem == "validate":
        if "pull_request:" not in text:
            errors.append(f"{path}: offline workflow must validate pull requests")
        if "contents: read" not in text:
            errors.append(f"{path}: offline workflow needs read-only permissions")
    elif "workflow_run:" not in text:
        errors.append(f"{path}: report workflow must be triggered by workflow_run")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    errors = []
    for path in sorted(args.directory.glob("*.yml")):
        errors.extend(validate_workflow(path, live=path.name in LIVE_WORKFLOW_NAMES))
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Validated {len(list(args.directory.glob('*.yml')))} workflow files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
