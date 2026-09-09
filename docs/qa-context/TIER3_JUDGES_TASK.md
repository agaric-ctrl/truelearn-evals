# Task: Build the Two Missing Tier 3 Judges (Non-Contradiction, Source-Coverage)

Read `docs/qa-context/MAESTRO_QA_FINDINGS.md` first. Like the Tier 1 task, this is scoped to avoid every unresolved fork listed there — it needs none of them resolved to proceed, and it needs no real golden data to *build* (only to eventually *trust at scale*, which is a separate later step).

## Why these two, and why now

Per Section 2 of the findings doc, the strategy-level rubric names two things this repo's existing three judges don't cover:
- **Non-contradiction** — does the output ever conflict with the retrieved grounding material? (Different from the existing faithfulness judge, which checks claim-traceability — a generation can be fully traceable to source and still contradict part of it, or vice versa.)
- **Source-coverage** ("completeness" in the strategy doc, disambiguated from the *structural* completeness check that already exists and is deterministic) — is everything supportable by the grounding material actually stated, or is real content being silently dropped? This is the literal inverse of faithfulness, not a rename of it.

Both are buildable today using the same synthetic-fixture discipline the existing three judges already use — i.e., hand-constructed input/output pairs with a known right answer, not real Maestro generations or real golden data. That's what makes this safe to build now: it doesn't wait on the golden-dataset-ownership question, and it doesn't wait on which observability tool gets chosen.

## The task

**1. Design the non-contradiction judge as its own mechanism, not a bolt-on to the existing faithfulness judge.** The two existing judge frameworks used in this repo each expose a single-purpose faithfulness metric — neither returns a contradiction signal as a second value from the same call. Getting both from one model call means writing a custom prompt that asks for both faithfulness and contradiction-detection in a single structured response, which means stepping outside those frameworks' packaged metrics for this specific check. Treat this as a deliberate, documented design decision, not an oversight if it doesn't reuse the existing metric plumbing directly.

**2. Design the source-coverage judge as the mirror image of the existing faithfulness check.** Faithfulness asks "does everything stated map to source"; this asks "does everything in source that should be stated actually appear." Same grounding material, opposite direction. Build and test them together where practical, since they're two views of the same underlying comparison.

**3. Build both against synthetic fixtures first**, following the same fixture-construction pattern the existing three judges already use (check how those fixtures are structured before inventing a new format). Cover clear-pass and clear-fail cases for each judge deliberately — a contradiction fixture should contain an unambiguous, constructed contradiction; a coverage-gap fixture should omit something a human would obviously expect to see.

**4. Do not build a fourth, single-model judge to "cover both at once" as a shortcut.** This repo's existing three-judge setup is deliberately redundant so that *disagreement between judges* is itself a signal — collapsing to one model, even for a new check, would remove that property for whatever it touches. If a single custom Claude call is used for the non-contradiction check per point 1, that's fine as a genuinely new, independently-designed check — it should not become a general-purpose replacement for the existing three.

**5. Write tests the same way the existing judge tests are written**, covering both judges' pass/fail synthetic fixtures.

## What this task does NOT include

- Running either judge against real Maestro output — that's a separate, later step once real content exists to feed it.
- Calibrating thresholds against real SME-labeled data — not possible yet; ship with a clearly-marked placeholder threshold, same caveat as the Tier 1 readability check.
- Wiring these into the golden-set import/gate pipeline — that's downstream of the golden-dataset-ownership question in the findings doc, out of scope here.

## CI wiring

Add both judges' synthetic-fixture test suites to the existing judge-vs-judge comparison job that already runs on synthetic fixtures for the other three judges — same trigger, same place, no new job needed for this.

## Acceptance criteria

- Both judges pass their own synthetic pass/fail fixtures.
- Neither judge is wired into a real golden-set pipeline yet (that's future work, blocked on ownership questions).
- The design decision in point 1 (custom prompt vs. framework-native metric) is documented inline, not silently chosen.
- No golden data, no live Maestro output, no architecture-fork resolution required to complete this task.

## When done

Summarize: how you structured the two judges relative to each other and to the existing three, what the synthetic fixtures look like, and what threshold placeholders you used (so they're easy to find and replace once real calibration data exists).
