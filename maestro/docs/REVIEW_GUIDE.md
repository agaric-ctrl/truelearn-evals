# Maestro SME review guide

This file is a review aid for TrueLearn's Maestro QA/eval harness (see the root README, Part 1). It
is not a validated editorial review protocol, and no example in this repository has been
SME-approved.

## Suggested reviewer workflow

1. Open the review-pool spreadsheet (`.xlsx`) you were sent for your exam bank.
2. Grade each row independently: `grade` (`approve` / `reject` / `needs_revision`), `notes` for
   anything worth recording, and your own `reviewer_id` — record who you are yourself, don't leave
   it blank.
3. Do not try to unshuffle the rows or guess which real question a `display_id` corresponds to.
   Row order and identity are deliberately hidden from you so grading isn't biased by knowing which
   item came from where.
4. Save the completed file and hand it back for import. Only `grade`, `reviewer_id`, and `notes`
   are ever read back from your copy — everything else on the sheet is locked and read-only.
5. Before an `approved` record is fully trusted, a second reviewer should independently re-check a
   sample of the batch. Record that check as `second_reviewer_id`/`second_reviewed_at` on the
   promoted record rather than re-running the whole import.
6. Never hand-edit `maestro/golden_data/*.jsonl` directly. Only the importer flips a record's
   `review_status` to `approved` — that's what keeps "every example is SME-verified before it counts
   as golden" actually true, not just documented.

## What you're actually assessing

You're judging whether `expected` is a genuinely good reference for `input` — is this a well-written,
accurate question (or edit, or article) for the stated topic and exam bank. You do **not** need to
re-check structural things like required fields, HTML validity, or duplicated tables — Tier 1's
deterministic checks already run automatically on every row before it can be promoted, and a row
that fails them is blocked regardless of your grade. If you notice something structurally off
anyway, mention it in `notes` — it's useful signal even though it isn't what blocks promotion.

## Placeholder files

- `maestro/golden_data/sme_roster.json` is a copyable reviewer-assignment record with no real
  identifying information filled in yet.
- `maestro/examples/sample_golden_batch.jsonl` contains starter example candidates for trying the
  generate → grade → import loop; none of it is real golden content.

Do not put real reviewer names, emails, patient/student identifiers, or contact information in this
repository. This repository is an evaluation harness, not a records system.
