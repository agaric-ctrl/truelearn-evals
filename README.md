# TrueLearn Evals

TrueLearn's home for AI-content evaluation harnesses. This is **internal work in progress, not a
released product** — see [LICENSE](LICENSE).

This repo grew out of a personal side project ([evaluations/faithfulness/](evaluations/faithfulness/))
built to learn how LLM-judge evaluation actually works, using generic clinical-QA content, not
TrueLearn data. That project is still here, still referenced, and still useful on its own — see its
[own README](evaluations/faithfulness/README.md) for what it is and how to run it. Everything below
is about the project that came after it: a real QA/eval harness for **Maestro**, TrueLearn's
AI content-generation backend being integrated into the Payload CMS editorial tool.

## Repository layout

```
.
├── maestro/                    # Maestro QA/eval harness (the active project - see below)
├── evaluations/faithfulness/   # the side project this repo started as - own README, still used
├── tools/                      # shared infrastructure (result schema, retries, HTML reports, ...)
│                               # - used by both projects above
├── docs/qa-context/            # Maestro's design history, open questions, and task docs
├── run_unit_tests.sh           # run Maestro's unit test suite - everything, or one file/class/test
├── run_evals.sh                # run Maestro's Tier 1 checks against real staged content
└── LICENSE
```

`maestro/CLAUDE.md` is Maestro's own quick-reference (loads automatically at the start of a Claude
Code session in this repo) — read it first for anything Maestro-related. `docs/qa-context/` holds
the full detail behind it: findings from TrueLearn's own architecture discussions, and one task doc
per major piece of work, each stating its own status.

## What's built

- **Tier 1 (deterministic checks)** — 13 rule-based checks against a generated question or article
  (required fields, HTML validity, table duplication, reference format, readability, markdown
  hygiene, and more — see `maestro/checks/`). Runs on every PR. Also runs against **real** staged
  Editorial content (see below) via `./run_evals.sh`, which produces a readable HTML report.
- **Tier 2 (golden set)** — schema + SME review-pool generate/import workflow
  (`maestro/golden/`), so approved content can become a reference set other things get scored
  against.
- **Tier 3 (LLM judges) — experimental.** Three independently-implemented judges (deepeval, RAGAS,
  a Promptfoo rubric) for faithfulness scoring, plus a script to compare their verdicts against each
  other. Validated only against 6 hand-written synthetic cases — **not real SME judgment** — off by
  default, not wired into any gate. Treat every verdict as not-yet-evidence.
- **Real Editorial content, staged as a draft proposal** — real question-bank/image-catalog/
  reference-article assets from Editorial's Biochemistry bank, tiered and run through Tier 1 for
  real (`maestro/golden_data/`, `docs/qa-context/EDITORIAL_ASSETS_STAGING_TASK.md`). Explicitly not
  adopted golden data — promotion is blocked on SME assignment, same as Tier 2 above.
- **Golden-set import reporting** — a plain-language throughput summary (approved/rejected/why) for
  a review-pool import run, for an SME/editorial audience (`maestro/golden/import_summary.py`).
- **Local dev tooling** — `run_unit_tests.sh` (one command for the whole test suite, or one file/class/
  test) and `run_evals.sh` (one command for a real Tier 1 content report), both mirroring what CI
  actually runs so there's no "passed for me" vs. "passed in CI" drift.

## What's not built yet

- **No connection to live Maestro.** Everything above runs against synthetic fixtures or a static
  snapshot of real Editorial content — nothing here calls Maestro/Payload in real time. The seam for
  it exists (`maestro/ingestion/`) but its `fetch_raw_candidates()` deliberately raises
  `NotImplementedError`: the real API endpoint, auth scheme, and response shape aren't confirmed yet.
- **Tier 3's remaining judges** (non-contradiction, source-coverage) — not started.
- **Comparative A/B testing** (e.g. prompt-merging vs. RAG) — not started.
- **A runtime quality gate** (block/flag content before it ships) — scoping only, blocked on an
  unresolved architecture question (see `maestro/CLAUDE.md`).
- **Several Tier 1 checks can't actually fail yet** — readability, redundancy, and parts of the
  reference-format check always report "Skipped" because no one has confirmed a real target value
  (a reading-level range, a citation style, etc.). See
  `docs/qa-context/EDITORIAL_TIER1_THRESHOLDS_QUESTIONS.md` — a live, open set of questions for
  Editorial that would unblock these.
- **An SME roster.** `maestro/golden_data/sme_roster.json` ships with all three exam banks
  unassigned — nothing can be promoted to golden data without a real person grading it.

For the full, current list of open questions and decisions still needed from TrueLearn (not
guessed at anywhere in this repo), see `docs/qa-context/MAESTRO_QA_FINDINGS.md` and the top of
`maestro/CLAUDE.md` — both are kept current; this README isn't the place to duplicate them.

## Quickstart

```bash
python3 -m venv .venv-maestro
.venv-maestro/bin/pip install -r requirements-maestro.txt
```

Two different commands, for two different questions:

```bash
./run_unit_tests.sh   # does the CODE work? unit tests, no report - just pass/fail. Takes an
                       # optional file/class/test argument to run just that instead of everything
                       # - see the usage comment at the top of run_unit_tests.sh for examples.

./run_evals.sh         # what does Tier 1 find in real CONTENT? runs the checks against real
                       # staged Editorial content and writes a readable HTML report per exam bank
```

See `docs/qa-context/` for everything else — each task doc explains what it built, why, and what
it's still waiting on.

## License

Proprietary — see [LICENSE](LICENSE). This is internal TrueLearn work in progress, not a released
product.
