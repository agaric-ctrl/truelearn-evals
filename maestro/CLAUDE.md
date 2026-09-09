# Maestro QA/Eval — Quick Reference

This file loads automatically at the start of every Claude Code session in this repo. Keep it short — it costs context even for unrelated tasks. Full detail lives in `docs/qa-context/`; read the relevant file there before doing any QA/eval-harness work.

## Settled facts — don't re-derive or re-litigate these

- **Maestro is not RAG.** It uses an agentic document-to-prompt merging workflow — no vector store, no chunking, no shared retrieval infra with other TrueLearn search initiatives. (Confirmed directly by Data Science lead.)
- **Faithfulness ≠ non-contradiction.** For articles, the model's own medical knowledge writes the bulk of the content; retrieved questions constrain (terminology, tested associations) rather than source it. Don't build/grade "claim traces to retrieved source" for articles — it fails by design. Check contradiction-rate + terminology alignment instead.
- **Bank-fidelity is not ground truth for accuracy.** Grading against previously-approved content as if it were correctness is wrong — new-topic banks have nothing to check against, medicine changes, some approved content is itself outdated.
- **No eval harness existed at the strategy level as of early Sep** (confirmed independently by two separate leads), even though this repo already has a working Tier 1/2/3 harness — the repo is ahead of what's been formally decided, not behind it.
- **Maestro is still a POC, not in production.** No formal release process, no defined SME escalation/rollback authority yet.
- **Deterministic approximation of length/depth/density/style is explicitly endorsed** by the Engineering/Platform lead, with named tools: markdownlint-style structural validation, py-readability-metrics-style readability scoring.

## Resolved as of Sep 9 (were previously listed as unresolved forks — don't re-litigate)

- **Sidecar eval service vs. library/pytest-based harness: these are complementary, not competing.** Confirmed by Data Science lead (Sep 9): "RAGAS is the framework/library, while sidecar service is the pipeline that would run/orchestrate those RAGAS evaluations." This repo's existing library harness (which already uses RAGAS as one of its three Tier 3 judges) can be the thing a future sidecar service orchestrates — not a rival architecture to it.
- **A/B testing of architectural variants is confirmed complementary to, not a replacement for, existing calibration checks.** Confirmed by Data Science lead (Sep 9): "I think these two are complementary... we need another subsection for [A/B testing]." Build both; don't treat one as superseding the other.

## Genuinely unresolved — do not silently pick a side

- **Observability tooling: Langfuse vs. NewRelic.** Still unresolved as of Sep 9 — Engineering/Platform lead asked Data Science lead directly whether Langfuse is used anywhere else; answer was "I don't know... happy to connect on this." Actively being worked, not stalled, but not decided.
- **Golden dataset ownership**: Editorial/SMEs must own curating and versioning it; QA/Engineering should not unilaterally assemble it.

## PENDING REPLY — question posted Sep 9, 10:31 AM ET, awaiting Data Science confirmation

A live architecture-review meeting (Sep 9) presented a slide claiming **"Grounded in our content — semantic search over 7,345 approved questions, embeddings held in Snowflake"** as a current, shipped property. On the same morning, in writing, the Data Science lead stated: **"Document-to-prompt merging is the current implementation for the POC. Moving to a shared Bedrock KB / RAG infrastructure remains an architectural candidate that we want to benchmark against."**

These directly conflict. Either the semantic-search/Snowflake-embeddings capability shipped very recently (between the doc comment and the meeting), or the meeting slide is describing the not-yet-adopted RAG candidate as if it were current production behavior. **A direct confirmation request was posted Sep 9, 10:31 AM ET, in the same comment thread** (asking whether the slide describes the target/candidate architecture rather than what's live today). As of this doc's last update, no reply yet. **Do not build or revise anything assuming either version is settled until the reply lands** — it determines whether the faithfulness/non-contradiction split (Section 2 of the findings doc, built around "articles are not RAG-sourced") is still correctly scoped. Check this thread for a reply before running Prompt 1 (Tier 3) or Prompt 4 (Comparative) from the build prompts.

## Full context

- `docs/qa-context/MAESTRO_QA_FINDINGS.md` — comprehensive findings from strategy doc + team discussion, reconciled against what's actually built in this repo.

## Task status (as of Sep 9)

- `docs/qa-context/TIER1_CHECKS_TASK.md` — **DONE.** Deterministic content checks (Tier 1), all 7 checks integrated, tested, wired into CI (PR-blocking job + `maestro-tier1-content-report.yml` scheduled/manual report job). Reference only — nothing left to build here.
- `docs/qa-context/TIER3_JUDGES_TASK.md` — **OPEN.** Non-contradiction + source-coverage judges, built against synthetic fixtures. Confirmed not started (`maestro/judge/` audited directly, no such judges exist under any name). Note: may need a light revisit once the URGENT item above is resolved, since the judges are designed around "articles are not RAG-sourced."
- `docs/qa-context/REPORTING_SUMMARY_TASK.md` — **OPEN.** Golden-set import throughput summary. Confirmed not started (`.github/workflows/report.yml` is unrelated pre-existing judge-comparison infrastructure, not this).
- `docs/qa-context/COMPARATIVE_AB_TESTING_TASK.md` — **OPEN, now confirmed necessary (not just proposed).** Data Science lead confirmed this needs its own subsection, complementary to calibration checks. Confirmed not started (`.github/workflows/faithfulness-framework-evaluation.yml` is unrelated pre-existing judge-validation infrastructure, not this). Prompt-merging vs. RAG is now the single highest-priority variant pair to scaffold toward, given the URGENT item above.
- `docs/qa-context/EDITORIAL_ASSETS_STAGING_TASK.md` — **OPEN, not yet created in repo.** Stages Editorial's real question-bank, image-catalog, and reference-article assets as a **draft proposal**, not adopted golden data. Data architecture section corrected against confirmed `maestro/golden_data/` state (see task doc — it's essentially empty, no existing "approved" convention to build alongside).
- `docs/qa-context/RUNTIME_QUALITY_GATE_TASK.md` — **NEW, scoping only, not yet buildable.** Surfaced by the Sep 9 architecture meeting: the team named "no runtime quality check" as an explicit, undesigned risk in the live article pipeline, with "evaluation and refinement loop" as the proposed mitigation. This is this harness's actual mandate, stated by the team. Blocked on the URGENT item above and on confirming what "verify references" currently does mechanically.

**Still unassigned, flagged not forgotten**: style/tone consistency (needs a fixed-anchor-example architecture, different from every check above) has no owner in any task doc yet. Don't fold it into an existing task — it needs its own design pass.

Everything else (retrieval-quality tier, length/depth calibration baseline, article-specific checks, judge-accuracy tracking) is blocked on a decision or real data that doesn't exist yet — see the findings doc before attempting any of it.
