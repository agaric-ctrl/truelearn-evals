# Task: Integrate Tier 1 Deterministic Content Checks Demo

Read `docs/qa-context/MAESTRO_QA_FINDINGS.md` (and `CLAUDE.md` if not already loaded) before starting. This task is deliberately scoped to avoid every unresolved fork listed there (sidecar-vs-library architecture, Langfuse-vs-NewRelic, A/B-testing scope, golden-dataset ownership) — it needs none of them resolved to proceed.

## What exists to integrate

A small working demo (`deterministic_checks.py`, `run_demo.py`, `sample_articles/`) was built and run against real Editorial reference articles in a separate session — no live model calls, no golden data, no architecture decision required. These files should already be in this repo (check a scratch/staging location if you don't see them referenced elsewhere). If they're missing, ask before reconstructing from scratch — the exact implementation matters less than integrating it correctly.

## The task

**1. Integrate, don't just drop in.** Match this repo's existing Tier 1 conventions exactly: same result-object shape the existing checks already use, same directory, same field-name-list parameterization pattern already used for the existing content-agnostic checks (so these new checks are reusable for a second content type later without rework — see the findings doc's note on the golden-example schema already anticipating this).

**2. Specifically add these as new Tier 1 checks** (rename/refactor to match repo conventions — this is a starting implementation, not a final API):

- **Table abbreviation footnote check** — cross-checks every table's abbreviations against its footnote row. Rule: every abbreviation used anywhere in a table (headers, row headers, data cells) must appear in a final merged footnote row.
- **Teaching-case standard check** — enforces a hard 3-sentence ceiling per case, and requires the bolded "Key teaching:" sentence to appear inline, not starting a new paragraph.
- **Case numbering check** — cases must be sequentially numbered from 1, no gaps.
- **References format check** — this fills in an existing stub, not a new file: 3-5 references, reverse-chronological order, at most one of each of two specific citation types, excludes certain named non-authoritative sources. Check whether the existing stub already has partial logic before overwriting it.
- **Readability check** — adopt an actual readability-metrics library (py-readability-metrics or equivalent), not a hand-rolled formula — this is the specific tool named in the findings doc, not a generic "Flesch or equivalent" placeholder. **The demo version used an illustrative target band that is not calibrated to anything real.** Implement the threshold as configurable and clearly marked as a placeholder — real calibration needs golden-set data that doesn't exist yet.
- **Markdown/payload structural compatibility check** — adopt an actual markdown-linting tool (markdownlint or a Python equivalent), not just the bespoke table/footnote logic above. This is a distinct, named check from the findings doc — general payload markdown compatibility, separate from the content-specific rules (footnotes, teaching cases, references).
- **Density/redundancy check (new — this fills a real gap, not in the original demo)** — an n-gram-overlap-based check for whether sentences within a single generation restate each other rather than each carrying new information. This is the deterministic tool named in the findings doc as planned (n-gram-based metrics), and is the most direct way to approximate "density/padding" from the strategy doc's rubric, which had no owner in the original demo. Compare each sentence's n-grams against prior sentences in the same section; flag high-overlap pairs as a padding signal. Same caveat as readability: ship with a placeholder threshold, not a validated one.
- **Arrow-style check** — flags a typed `->` where house style requires an arrow character.

**Note on what's still unassigned after this task**: style/tone consistency (per the findings doc, this needs comparison against 2-3 fixed approved examples per bank, not per-generation retrieved context — a genuinely different architecture from every check above) still has no owner across any task doc in this repo. Don't fold it into this task; it needs its own design decision, flagged separately.

**3. Fix known limitations, don't inherit them silently.** The demo's abbreviation-detection logic has real false positives (flagging chemical-formula fragments and vitamin/label names that aren't actually undefined abbreviations). Build a small allowlist/exclusion mechanism, following whatever pattern the existing required-field check already uses for its own allowlisting, rather than shipping the naive version.

**4. Write tests the same way the existing ~118 tests are written** — synthetic fixtures covering both the pass and fail path for each rule, not just the happy path, following existing test-file and venv conventions.

## CI wiring

Add these checks to the existing PR-triggered Tier 1 job — same trigger, same blocking behavior as the other deterministic checks already there (they're cheap and deterministic; no reason to treat them differently).

**Also add a separate, manually/schedule-triggered job** that runs these checks against a directory of sample or real content and produces a human-readable report — reuse the styled-HTML, pass/fail-badge, honest-limitations-callout approach from the original demo rather than just printing raw test output, since the point of this tier is that non-engineers can review it without reading code.

**On the sidecar-vs-library question**: don't resolve it here. But note, as a comment in the workflow file and worth raising back to the team rather than deciding unilaterally: a workflow with both a PR trigger and a manual/scheduled trigger already provides "runs on-demand and in CI/CD" for this specific check category, without a separately deployed service. That may or may not satisfy what was meant by the sidecar proposal — flag it, don't assume it settles the question.

## Acceptance criteria

- All new checks pass on synthetic fixtures testing both the pass and fail path.
- The PR-triggered job runs these on every PR, same as existing Tier 1 checks.
- The manual/scheduled job produces a shareable HTML report.
- No live model calls anywhere in this task. No golden-dataset dependency. No architecture decision (sidecar vs. library, observability tool, A/B-testing scope) gets silently resolved by this work — if you find yourself needing to decide one of those to proceed, stop and flag it instead of picking a default.
- Don't touch the still-stubbed table-placement check (correctly blocked on unconfirmed bank-specific rules) or anything in generation, ingestion, or the three Tier 3 judges — out of scope here.

## When done

Summarize: what you integrated vs. what had to be redesigned from the demo version, what the false-positive fixes ended up looking like, and what a real CI run actually shows.
