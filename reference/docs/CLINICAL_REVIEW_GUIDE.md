# Clinical review placeholder

This file is a review aid for the faithfulness-eval reference methodology described in the root
README (Part 2) — a supporting reference implementation used to prototype judge-testing discipline,
not TrueLearn production content. It is not a clinical validation protocol, and no case in this
repository has been clinician-approved.

## Suggested reviewer workflow

1. Open [`data/gold_cases.json`](../data/gold_cases.json).
2. Review the source, answer, expected verdict, and each claim independently.
3. Record a reviewer identifier, date, decision, and notes in the case or in a
   separate copy of the review template.
4. Resolve disagreements with a second reviewer before changing a production
   benchmark.
5. Only change `review_status` to `approved` after qualified review. Keep
   `pending_clinician_review` for cases that have not been reviewed.

Reviewers should assess faithfulness to the supplied source, not whether the
answer is generally medically correct. A faithful answer can still be unsafe
or incomplete; record those concerns in `review_notes` rather than changing
the faithfulness verdict without documenting why.

## Placeholder files

- [`data/clinical_review_template.json`](../data/clinical_review_template.json)
  is a copyable review record with no identifying information.
- [`data/gold_cases.json`](../data/gold_cases.json) contains the starter cases
  and remains explicitly pending review.

Do not put patient identifiers, real clinical notes, or contact information in
this repository. This repository is an evaluation harness, not a clinical review
system.
