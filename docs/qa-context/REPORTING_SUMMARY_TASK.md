# Task: Golden-Set Import Throughput Summary

Read `docs/qa-context/MAESTRO_QA_FINDINGS.md` Section 4 first. This is the smallest of the three currently-buildable tasks, included for completeness rather than urgency.

## The gap

This repo's existing golden-set import tooling already produces an outcome (promoted / blocked / reason) for every item it processes, but nothing currently reads that output after the fact — it's computed and discarded. There is no visibility today into promotion rates, rejection reasons, or throughput over time, for any audience (engineering, SME/editorial leads, or leadership).

## The task

**1. Write a small script that summarizes the existing import tooling's per-run output**: counts of promoted/blocked/skipped, grouped by reason and by exam bank or content-area tag if that grouping is already available in the data. Read from whatever the import tool already produces — don't change the import tool itself to emit something new unless the current output genuinely lacks the fields needed.

**2. Push the summary somewhere lightweight** — a committed markdown file updated on each run, a message to wherever the team already looks (a chat channel, if there's an existing integration to reuse), or a plain object in cloud storage if one is already used elsewhere in this pipeline (per the findings doc, cloud storage for eval results was independently suggested as a "broadly accessible location" option). Any of these is fine — the point is this doesn't need a sidecar service or a dashboard to be useful, and shouldn't wait on that architecture question being resolved. Don't build a dashboard or a new service for this; the whole point is that it's cheap.

**3. Design for the audience that actually needs this first**: per the findings doc, this is explicitly for SME/editorial-lead visibility into throughput — not engineering (already served by existing CI pass/fail) and not leadership trend reporting (which needs real historical data to be meaningful, and doesn't exist yet regardless of what this script does).

## What this task does NOT include

- Any judge-accuracy-over-time or retrieval-quality trend reporting — both blocked on real SME-labeled data that doesn't exist yet. Don't build placeholders for these; there's nothing meaningful to show yet.
- Any UI or dashboard — text/markdown output is sufficient for this task.
- A decision on whether this eventually becomes part of a sidecar service or stays a repo script — per the findings doc, that architecture question is unresolved; keep this small enough that it isn't a meaningful cost either way.

## CI wiring

If there's an existing scheduled or post-merge job that already runs the import tooling, hook this summary to run immediately after it, using whatever output the import step already produces in that job. If no such job exists yet, this can run as a manual/on-demand script for now — don't build new CI infrastructure just to host this one summary.

## Acceptance criteria

- Running the script against a sample import run produces a readable summary (counts + reasons + grouping).
- No new golden data, no live model calls, no architecture decision required.
- Output format is simple enough that an SME/editorial lead can read it without engineering help.

## When done

Summarize: what fields the existing import output already had vs. what (if anything) needed to change to produce a useful grouping, and where you ended up pushing the summary.
