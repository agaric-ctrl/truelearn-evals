"""Comparative (A/B) testing scaffold for architectural variants -
docs/qa-context/COMPARATIVE_AB_TESTING_TASK.md.

Confirmed-necessary scope as of Sep 9 (not a hedge against an open question - see the task doc's
own Sep 9 update and maestro/CLAUDE.md's "Resolved as of Sep 9" section): Data Science confirmed
comparative testing of architectural variants (prompt-merging vs. RAG, structured vs. unstructured
output, short vs. long chat history, single-step vs. multi-step generation, sequential vs.
draft-review-rewrite) is complementary to, not a replacement for, the existing absolute-rubric
calibration checks (Tier 1/Tier 3 above). Build both; this package is the "both" for comparative
testing specifically.

Built on the team's WORKING INTERPRETATION of the still-unresolved PENDING REPLY item in
maestro/CLAUDE.md (document-to-prompt merging is current; RAG is a benchmark candidate, not
shipped) - NOT a formally confirmed fact. This matters more here than for the Tier 3 judges: once
real prompt-merging vs. RAG generation variants exist, comparing them is this scaffold's
highest-priority first real use case. If that interpretation turns out to be wrong, the SCAFFOLD
itself (variant-pair shape, comparison runner, diff logic) still holds - only the specific
"which two variants to compare first" framing would need revisiting, not the mechanism.

**No judgment logic decides "which variant is better" anywhere in this package.** Every module here
either runs existing Tier 1/Tier 3 checks or diffs their already-produced results - never scores,
weights, or ranks the two variants against each other. A human (SME, Editorial, whoever owns this
decision) reads the diff and decides what it means, same principle already applied to Tier 2 (SME
grading, not an automated verdict).

Off by default: manual/on-demand only (see run_variant_pair.py's own CLI), never wired into the
PR-blocking job - comparative runs are exploratory by nature, not a pass/fail gate.
"""
