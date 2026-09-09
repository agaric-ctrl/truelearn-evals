# Maestro QA/Eval — Quick Reference

This file loads automatically at the start of every Claude Code session in this repo. Keep it short — it costs context even for unrelated tasks. Full detail lives in `docs/qa-context/`; read the relevant file there before doing any QA/eval-harness work.

## Settled facts — don't re-derive or re-litigate these

- **Maestro is not RAG.** It uses an agentic document-to-prompt merging workflow — no vector store, no chunking, no shared retrieval infra with other TrueLearn search initiatives. (Confirmed directly by Data Science lead.)
- **Faithfulness ≠ non-contradiction.** For articles, the model's own medical knowledge writes the bulk of the content; retrieved questions constrain (terminology, tested associations) rather than source it. Don't build/grade "claim traces to retrieved source" for articles — it fails by design. Check contradiction-rate + terminology alignment instead.
- **Bank-fidelity is not ground truth for accuracy.** Grading against previously-approved content as if it were correctness is wrong — new-topic banks have nothing to check against, medicine changes, some approved content is itself outdated.
- **No eval harness existed at the strategy level as of early Sep** (confirmed independently by two separate leads), even though this repo already has a working Tier 1/2/3 harness — the repo is ahead of what's been formally decided, not behind it.
- **Maestro is still a POC, not in production.** No formal release process, no defined SME escalation/rollback authority yet.
- **Deterministic approximation of length/depth/density/style is explicitly endorsed** by the Engineering/Platform lead, with named tools: markdownlint-style structural validation, py-readability-metrics-style readability scoring.

## Genuinely unresolved — do not silently pick a side

- **Sidecar eval service** (on-demand + CI/CD, results in S3 — Engineering/Platform lead's proposal) **vs. this repo's existing library/pytest-based harness.** Unreconciled.
- **Observability tooling: Langfuse vs. NewRelic.** Unresolved between Data Science lead and Engineering/Platform lead.
- **A/B testing of architectural variants may become the primary testing focus**, not just per-output rubric grading. Unresolved whether this replaces or runs alongside existing calibration checks.
- **Golden dataset ownership**: Editorial/SMEs must own curating and versioning it; QA/Engineering should not unilaterally assemble it.

## Full context

- `docs/qa-context/MAESTRO_QA_FINDINGS.md` — comprehensive findings from strategy doc + team discussion, reconciled against what's actually built in this repo.

## Active tasks (currently buildable — see findings doc for why these four and not others)

- `docs/qa-context/TIER1_CHECKS_TASK.md` — deterministic content checks (Tier 1), including the named tools (readability library, markdown linter, n-gram-based redundancy check).
- `docs/qa-context/TIER3_JUDGES_TASK.md` — non-contradiction + source-coverage judges (Tier 3), built against synthetic fixtures.
- `docs/qa-context/REPORTING_SUMMARY_TASK.md` — golden-set import throughput summary.
- `docs/qa-context/COMPARATIVE_AB_TESTING_TASK.md` — scaffold for comparing architectural variants, per Data Science lead's direction that testing scope should center on this. Builds the mechanism only; does not decide whether this replaces or supplements calibration checks.

**Still unassigned, flagged not forgotten**: style/tone consistency (needs a fixed-anchor-example architecture, different from every check above) has no owner in any task doc yet. Don't fold it into an existing task — it needs its own design pass.

Everything else (retrieval-quality tier, length/depth calibration baseline, article-specific checks, judge-accuracy tracking) is blocked on a decision or real data that doesn't exist yet — see the findings doc before attempting any of it.
