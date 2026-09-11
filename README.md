# TrueLearn Evals

## Experimental

This repository began as a personal experiment in LLM-judge evaluation using generic clinical-QA
content, not TrueLearn data. That reusable work remains in
[`evaluations/faithfulness/`](evaluations/faithfulness/); its
[README](evaluations/faithfulness/README.md) explains what it does and how to run it. The repository
now also contains exploratory QA/evaluation tooling for **Maestro**, TrueLearn's AI
content-generation backend.

This is experimental QA/evaluation tooling, not production infrastructure. Nothing here gates or
blocks real content today: Tier 1 checks report findings but are not an article-promotion gate, and
the five Tier 3 LLM judges have not been validated against real SME judgment. The repository does
not connect to live Maestro/Payload output yet. See Status below for what is built and what remains
open.

## Repository layout

```
.
├── maestro/                    # exploratory Maestro QA/eval tooling (the active project)
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

## Status

### Done

- **Tier 1 deterministic checks** — 13 checks in `maestro/checks/`, run via `maestro/runner.py`;
  PR-blocking in `validate.yml`.
- **Tier 1 run against real content** — `./run_evals.sh` converts Editorial's 3 real Biochemistry
  `.docx` articles and checks the 71 staged questions, writing two HTML reports.
- **Tier 2 golden set** — `GoldenExample` schema + blind SME review pool as an Excel round-trip
  (`generate_pool.py` exports, `import_pool.py` re-imports and gates on Tier 1).
- **Golden-set import summary** — `import_pool.py --outcomes-json` feeds `import_summary.py`, which
  writes an approved/rejected/why markdown summary; runs in the existing CI smoke test.
- **Editorial assets staged** — `stage_editorial_assets.py` tiered the real question bank into 71
  drafts, 40 image-relevance pairs, 33 article fixtures, under `golden_data/staging/`, checksummed
  against a manifest.
- **Tier 3 faithfulness judges (3)** — deepeval, RAGAS, and a Promptfoo rubric, independently
  implemented so disagreement between them is itself a signal; `compare_gold_suites.py` diffs them.
- **Tier 3 non-contradiction judge** — custom Claude prompt returning structured JSON (no packaged
  metric in either framework does contradiction); threshold `MAX_ALLOWED_CONTRADICTIONS = 0`.
- **Tier 3 source-coverage judge** — custom Claude prompt decomposing the source and scoring
  covered/total; threshold `COVERAGE_THRESHOLD = 0.8`. **Exam questions only — not valid for
  articles** (see `source_coverage.py`'s SCOPE section).
- **Comparative (A/B) scaffold** — `maestro/comparative/`: variant pair in, Tier 1 + available
  judges run per side, side-by-side HTML diff out. Manual-dispatch workflow only. No logic picks a
  winner.
- **Test + eval runners** — `run_unit_tests.sh` (241 tests across two venvs) and `run_evals.sh`,
  running the same commands CI runs.

### Not done

- **Runtime Quality Gate** — scoping doc only; blocked on the two Pending questions below.
- **Terminology / tested-association alignment for articles** — the check articles need in place of
  source-coverage. No task doc, no owner.
- **Style/tone consistency check** — needs a fixed-anchor-example design, unlike every existing
  check; deliberately not folded into another task.
- **Live Payload ingestion** — `ingestion/payload_api.py`'s `fetch_raw_candidates()` raises
  `NotImplementedError`; stopped deliberately at the unconfirmed API boundary rather than guessing
  an endpoint.
- **Articles through the golden-set gate** — `import_pool.py` runs no Tier 1 gate for articles and
  ingestion skips article-shaped payloads; article checks currently run outside that path.
- **Judges validated against real SME grading** — deferred until graded golden data exists; all 5
  are validated only against hand-written synthetic fixtures.
- **Promptfoo suite run live** — verified only against its fixture; no Node in the dev environment,
  and it is never auto-run in CI.
- **Prompt-merging vs. RAG comparison** — the scaffold's intended first use; both variants must
  exist in Maestro before a real pair can be built.
- **Retrieval-quality tier** — needs relevant-vs-retrieved human labels, a third labeling task on
  top of one that is already unstaffed.

### Pending

- **Is article grounding document-to-prompt merging or RAG?** An architecture-review slide
  described semantic search over 7,345 questions with Snowflake embeddings as shipped, while the
  Data Science lead separately stated that document-to-prompt merging is current and RAG remains
  a benchmark candidate. Clarification has been requested and is still pending. Tier 3 and the
  A/B scaffold currently follow the document-to-prompt merging interpretation.
- **What does the pipeline's "verify references" step do?** Real citation confirmation, or
  format/URL-resolution only — unconfirmed. Blocks the Runtime Quality Gate scope.
- **Tier 1 threshold values from Editorial** — reading-level range, redundancy tolerance, citation
  style, capped citation types, excluded sources, table placement, whether Bottom Line is required.
  Until these are set, readability, density/redundancy, table-placement, and parts of
  `references_format` and `field_constraints` always report Skipped. Asked in
  `docs/qa-context/EDITORIAL_TIER1_THRESHOLDS_QUESTIONS.md`; no answer yet.
- **Does the 3–5 references rule apply to individual questions?** All 71 staged questions fail it
  with 0 references; the rule may have been written for articles. Flagged in the same doc.
- **Who are the SME reviewers?** `golden_data/sme_roster.json` has all three exam banks unassigned,
  so nothing has been promoted to golden data (`golden_data/*.jsonl` does not exist yet). A Content
  Team lead was named as the contact; no one is formally assigned.
- **Langfuse or NewRelic for tracing?** Unresolved as of Sep 9; the two leads agreed to connect
  directly. Nothing in the repo depends on the answer yet.

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
