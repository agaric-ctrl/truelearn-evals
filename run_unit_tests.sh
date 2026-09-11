#!/usr/bin/env bash
# One command to run Maestro's UNIT TESTS - either everything, or one file/class/test - and get a
# clear pass/fail answer. This proves the CODE works (does a check/judge/script do what its own
# tests say it should) - it does NOT run the checks against real content. For that, see
# ./run_evals.sh instead.
#
# This exists because remembering two venvs and nine file paths isn't a real interface - and
# whatever a human runs locally should be exactly what CI runs too, so there's no drift between
# "it passed for me" and "it passed in CI". .github/workflows/validate.yml runs the same
# underlying commands, split into separately-named steps for per-step visibility in the GitHub
# Actions UI; this script runs the same suites (or a single target) in one shot for local use.
#
# Usage:
#   ./run_unit_tests.sh                                                        # everything
#   ./run_unit_tests.sh maestro/test_maestro.py                                # one file
#   ./run_unit_tests.sh maestro.test_maestro.TableAbbreviationFootnotesTests   # one class (dotted form)
#   ./run_unit_tests.sh maestro.test_maestro.TableAbbreviationFootnotesTests.test_complex_roman_numeral_not_flagged  # one test
#
# A single target only ever needs one venv, so it's picked automatically: anything under
# test_judge_ragas (file or dotted form) runs in .venv-maestro-ragas; everything else runs in
# .venv-maestro. With no argument, both suites run, same as before.
#
# Output:
#   - Full test output streamed to the terminal AND saved to test-results.log (so there's always
#     a file to open afterward, not just scrollback).
#   - A final PASSED/FAILED summary, in plain text, impossible to miss.
#   - Exit code 0 if everything passed, 1 otherwise - safe to use as a CI gate directly.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

LOG_FILE="test-results.log"
: > "$LOG_FILE"  # truncate/create fresh each run - this log is always this run's results, not a growing history

MAIN_TEST_FILES=(
  maestro/test_maestro.py
  maestro/test_golden.py
  maestro/test_judge.py
  maestro/test_generation.py
  maestro/test_ingestion.py
  maestro/test_judge_compare.py
  maestro/test_judge_promptfoo_suite.py
  maestro/test_import_summary.py
  maestro/test_editorial_staging.py
  maestro/test_judge_non_contradiction.py
  maestro/test_judge_source_coverage.py
  maestro/test_comparative.py
)

if [ ! -x ".venv-maestro/bin/python" ]; then
  echo "ERROR: .venv-maestro not found. Set it up first:" | tee -a "$LOG_FILE"
  echo "  python3 -m venv .venv-maestro && .venv-maestro/bin/pip install -r requirements-maestro.txt" | tee -a "$LOG_FILE"
  exit 1
fi

TARGET="${1:-}"

if [ -n "$TARGET" ]; then
  # Single-target mode: run just the file/class/test the caller named, in whichever venv it needs.
  case "$TARGET" in
    *test_judge_ragas*)
      if [ ! -x ".venv-maestro-ragas/bin/python" ]; then
        echo "ERROR: .venv-maestro-ragas not found. Set it up first:" | tee -a "$LOG_FILE"
        echo "  python3 -m venv .venv-maestro-ragas && .venv-maestro-ragas/bin/pip install -r requirements-maestro-ragas.txt" | tee -a "$LOG_FILE"
        exit 1
      fi
      echo "=== $TARGET (.venv-maestro-ragas) ===" | tee -a "$LOG_FILE"
      .venv-maestro-ragas/bin/python -m unittest -v "$TARGET" 2>&1 | tee -a "$LOG_FILE"
      STATUS=${PIPESTATUS[0]}
      ;;
    *)
      echo "=== $TARGET (.venv-maestro) ===" | tee -a "$LOG_FILE"
      .venv-maestro/bin/python -m unittest -v "$TARGET" 2>&1 | tee -a "$LOG_FILE"
      STATUS=${PIPESTATUS[0]}
      ;;
  esac

  echo | tee -a "$LOG_FILE"
  echo "================================================================" | tee -a "$LOG_FILE"
  if [ "$STATUS" -eq 0 ]; then
    echo "ALL TESTS PASSED" | tee -a "$LOG_FILE"
    echo "================================================================" | tee -a "$LOG_FILE"
    echo "Full output saved to: $LOG_FILE"
    exit 0
  else
    echo "SOME TESTS FAILED - scroll up (or open $LOG_FILE) to see which one" | tee -a "$LOG_FILE"
    echo "================================================================" | tee -a "$LOG_FILE"
    echo "Full output saved to: $LOG_FILE"
    exit 1
  fi
fi

echo "=== Main Maestro test suite (${#MAIN_TEST_FILES[@]} files, .venv-maestro) ===" | tee -a "$LOG_FILE"
.venv-maestro/bin/python -m unittest -v "${MAIN_TEST_FILES[@]}" 2>&1 | tee -a "$LOG_FILE"
MAIN_STATUS=${PIPESTATUS[0]}

echo | tee -a "$LOG_FILE"

if [ -x ".venv-maestro-ragas/bin/python" ]; then
  echo "=== RAGAS-judge test suite (.venv-maestro-ragas - separate venv, click conflicts with deepeval) ===" | tee -a "$LOG_FILE"
  .venv-maestro-ragas/bin/python -m unittest -v maestro/test_judge_ragas.py 2>&1 | tee -a "$LOG_FILE"
  RAGAS_STATUS=${PIPESTATUS[0]}
else
  echo "=== RAGAS-judge test suite SKIPPED: .venv-maestro-ragas not found ===" | tee -a "$LOG_FILE"
  echo "  Set it up with: python3 -m venv .venv-maestro-ragas && .venv-maestro-ragas/bin/pip install -r requirements-maestro-ragas.txt" | tee -a "$LOG_FILE"
  RAGAS_STATUS=0  # not a failure - just not set up; don't block on an optional environment
fi

echo | tee -a "$LOG_FILE"
echo "================================================================" | tee -a "$LOG_FILE"
if [ "$MAIN_STATUS" -eq 0 ] && [ "$RAGAS_STATUS" -eq 0 ]; then
  echo "ALL TESTS PASSED" | tee -a "$LOG_FILE"
  echo "================================================================" | tee -a "$LOG_FILE"
  echo "Full output saved to: $LOG_FILE"
  exit 0
else
  echo "SOME TESTS FAILED - scroll up (or open $LOG_FILE) to see which one" | tee -a "$LOG_FILE"
  echo "  main suite exit code:  $MAIN_STATUS" | tee -a "$LOG_FILE"
  echo "  ragas suite exit code: $RAGAS_STATUS" | tee -a "$LOG_FILE"
  echo "================================================================" | tee -a "$LOG_FILE"
  echo "Full output saved to: $LOG_FILE"
  exit 1
fi
