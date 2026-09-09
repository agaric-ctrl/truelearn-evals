# Task: Comparative (A/B) Testing Scaffold for Architectural Variants

Read `docs/qa-context/MAESTRO_QA_FINDINGS.md` Section 2 first. This task exists because the Data Science lead stated directly that testing scope "needs to center on" comparing architectural variants (prompt-merging vs. a hypothetical RAG approach, structured vs. unstructured output, short vs. long chat history, single-step vs. multi-step generation, sequential vs. draft-review-rewrite loop) — not just grading one pipeline's output against an absolute rubric. That's a stronger signal than "someday, maybe" and this repo currently has no mechanism for it at all.

**Update, Sep 9: this question is now answered.** The QA lead asked directly whether this replaces or runs alongside calibration checks; Data Science confirmed: "these two are complementary... we need another subsection for [A/B testing]." Build both — this is no longer a hedge against an open question, it's confirmed scope. Given the same-day conflict over whether RAG-style retrieval has actually shipped (see `CLAUDE.md`'s URGENT section), **prompt-merging vs. RAG is now the single highest-priority variant pair to build toward** once real generation variants exist to compare — not a hypothetical example among several.

## Why this is buildable now

A comparative-testing scaffold needs: (1) a way to run the same input through two different configurations, (2) a way to capture both outputs, (3) a way to run existing checks/judges against both and diff the results. None of that requires golden data, a resolved observability-tool fork, or a resolved sidecar-vs-library architecture decision — it's orthogonal to all three. It does need real Maestro output to be *useful*, same as everything downstream of the still-stubbed live ingestion API — but the scaffold itself can be built and tested with synthetic/mocked generations now, same as the Tier 1 and Tier 3 tasks.

## The task

**1. Define a "variant pair" data shape**: same input (topic, exam bank, whatever the generation entrypoint already takes), two labeled outputs (e.g. `variant_a`, `variant_b`, with a free-text label for what actually varied — "single-step" vs. "multi-step," etc.). Don't hardcode the specific variant axes named above into the schema — the axis being compared should be a label, not a fixed enum, since the list of interesting comparisons will grow.

**2. Build a comparison runner** that takes a variant pair and runs the existing Tier 1 deterministic checks and Tier 3 judges (including the two new ones from the Tier 3 task, once built) against both outputs independently, then produces a structured diff: which checks/judges disagreed between the two variants, and by how much for score-based judges.

**3. Do NOT build new judgment logic for "which variant is better."** That's a product/quality-bar decision, not something to encode as a threshold in this task. The scaffold's job is to surface the diff clearly (a human — SME, Editorial, or whoever owns this decision — decides what the diff means for a given comparison); this mirrors the same principle already applied to Tier 2 (SME grading, not an automated verdict).

**4. Reuse existing synthetic fixtures where possible** — construct variant pairs by hand for testing the scaffold itself (e.g., a "verbose" and "terse" hand-written version of the same content) rather than requiring real generations to validate that the comparison mechanism works.

**5. Design the output to be reviewable by a non-engineer**, same spirit as the Tier 1 HTML report — a side-by-side view showing both variants' outputs and where the checks/judges diverged, not just a JSON diff.

## What this task does NOT include

- Actually running this against real Maestro output for the specific variants named (prompt-merging vs RAG, etc.) — that depends on those variants existing to compare, which is a Maestro-engineering question, not a QA-harness one.
- Deciding whether this replaces or supplements the existing calibration checks — flagged as unresolved in the findings doc, stays unresolved here.
- Any new deterministic or judge-based check logic beyond what Tier 1/Tier 3 already provide — this task is about running existing checks twice and diffing, not inventing new ones.

## CI wiring

This likely doesn't belong in the PR-blocking job — comparative runs are exploratory/investigative by nature, not a pass/fail gate. A manual/on-demand trigger (same pattern as the Tier 1 report job) is the right fit: someone runs it deliberately when they want to compare two specific variants, rather than it running automatically on every change.

## Acceptance criteria

- The scaffold accepts a hand-constructed variant pair and produces a reviewable diff using existing Tier 1/Tier 3 checks.
- No new judgment logic decides "which variant wins" — the scaffold surfaces disagreement, it doesn't resolve it.
- Nothing here silently answers the "replace or supplement calibration" question — if that comes up, flag it rather than assuming an answer.

## When done

Summarize: what the variant-pair schema ended up looking like, what a sample diff output looks like end-to-end on a hand-constructed pair, and explicitly re-flag the still-unanswered "replace or supplement" question for whoever can actually decide it.
