#!/usr/bin/env bash
# One command to run Tier 1 (deterministic) checks against real staged content and get a report.
#
# This is the eval-content counterpart to run_unit_tests.sh: run_unit_tests.sh answers "does the code work"
# (unit tests, no report beyond pass/fail); this answers "what does Tier 1 find in real staged
# content" and always produces an HTML report you can open, because these checks are meant to be
# read by a human (SME/editorial), not just pass/fail'd.
#
# Scope, deliberately: THIS SCRIPT RUNS TIER 1 ONLY.
#   - Tier 2 (SME review-pool generation/import - maestro/golden/generate_pool.py,
#     import_pool.py) is a separate, human-in-the-loop workflow, not a "run and get a report"
#     step - not folded in here.
#   - Tier 3 (LLM judges: deepeval/RAGAS/Promptfoo + non-contradiction/source-coverage -
#     maestro/judge/, all 5 now built per docs/qa-context/TIER3_JUDGES_TASK.md) is NOT run here
#     either. Those make real, billed Anthropic API calls and need ANTHROPIC_API_KEY set - that's a
#     deliberate, explicit opt-in, not something that should fire every time someone wants a Tier 1
#     report. See maestro/judge/run_gold_suite*.py to run an individual judge directly by hand.
#   TODO (tracked, not done): once Tier 2/3 have their own "run and get output" shape decided,
#   give run_evals.sh a --tier flag (or a sibling script) rather than silently expanding this one.
#
# For each exam bank found under maestro/golden_data/manifests/, this runs Tier 1's content
# checks against two kinds of real staged content and writes two HTML reports:
#   1. The real reference articles (*.docx in manifests/<bank>/) via tier1_validate_articles.py
#      -> maestro/golden_data/staging/<bank>/tier1_validation_report.html
#   2. The staged question drafts (staging/<bank>/questions/*.json) via
#      tier1_validate_staged_questions.py
#      -> maestro/golden_data/staging/<bank>/tier1_questions_report.html
#
# Usage:
#   ./run_evals.sh              # all exam banks found under maestro/golden_data/manifests/
#   ./run_evals.sh biochemistry # just that one bank
#
# Output: one line per report written, with its path and FAIL count, plus a final summary saying
# where to look. Exit code is always 0 (Tier 1 FAILs are findings to review, not a broken build -
# unlike run_unit_tests.sh, this is not a pass/fail gate).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

if [ ! -x ".venv-maestro/bin/python" ]; then
  echo "ERROR: .venv-maestro not found. Set it up first:"
  echo "  python3 -m venv .venv-maestro && .venv-maestro/bin/pip install -r requirements-maestro.txt"
  exit 1
fi

MANIFESTS_DIR="maestro/golden_data/manifests"
STAGING_DIR="maestro/golden_data/staging"

if [ ! -d "$MANIFESTS_DIR" ]; then
  echo "ERROR: $MANIFESTS_DIR not found - nothing to run Tier 1 against."
  exit 1
fi

if [ $# -ge 1 ]; then
  BANKS=("$1")
else
  BANKS=()
  for dir in "$MANIFESTS_DIR"/*/; do
    [ -d "$dir" ] || continue
    BANKS+=("$(basename "$dir")")
  done
fi

if [ ${#BANKS[@]} -eq 0 ]; then
  echo "No exam banks found under $MANIFESTS_DIR/ (expected a subdirectory per bank, e.g. biochemistry/)."
  exit 1
fi

echo "Tier 1 only - see the top of this script for why Tier 2/3 aren't included."
echo

for BANK in "${BANKS[@]}"; do
  BANK_MANIFEST_DIR="$MANIFESTS_DIR/$BANK"
  BANK_STAGING_DIR="$STAGING_DIR/$BANK"

  if [ ! -d "$BANK_MANIFEST_DIR" ]; then
    echo "=== $BANK: SKIPPED - no directory at $BANK_MANIFEST_DIR ==="
    continue
  fi

  echo "=== $BANK ==="

  ARTICLES=("$BANK_MANIFEST_DIR"/*.docx)
  if [ -e "${ARTICLES[0]}" ]; then
    ARTICLE_REPORT="$BANK_STAGING_DIR/tier1_validation_report.html"
    .venv-maestro/bin/python maestro/golden/tier1_validate_articles.py \
      --reference-articles "${ARTICLES[@]}" \
      --out "$ARTICLE_REPORT"
  else
    echo "  (no reference articles found in $BANK_MANIFEST_DIR - skipping article report)"
  fi

  QUESTIONS_DIR="$BANK_STAGING_DIR/questions"
  if [ -d "$QUESTIONS_DIR" ] && [ -n "$(ls -A "$QUESTIONS_DIR"/*.json 2>/dev/null)" ]; then
    QUESTIONS_REPORT="$BANK_STAGING_DIR/tier1_questions_report.html"
    .venv-maestro/bin/python maestro/golden/tier1_validate_staged_questions.py \
      --questions-dir "$QUESTIONS_DIR" \
      --out "$QUESTIONS_REPORT"
  else
    echo "  (no staged question drafts found in $QUESTIONS_DIR - skipping questions report)"
  fi

  echo
done

echo "================================================================"
echo "Done. Open any *_report.html above in a browser to read the findings, e.g.:"
echo "  open $STAGING_DIR/${BANKS[0]}/tier1_validation_report.html"
echo "================================================================"
