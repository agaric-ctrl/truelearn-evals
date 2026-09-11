# Task: Runtime Quality Gate for the Live Article Pipeline (Scoping Only — Not Yet Buildable)

Read `docs/qa-context/MAESTRO_QA_FINDINGS.md` Section 7 first — this task exists entirely because of the Sep 9 architecture meeting, not because of anything in the original strategy doc.

## Why this task exists

The team presented a confirmed 9-step LangGraph pipeline (topic → normalize request → retrieve questions → identify template → filter relevance → verify references → draft article → embed images → assemble output → article) and, on the same slide set, explicitly named **"no runtime quality check"** as an open risk: *"unchecked execution errors propagate downstream."* Their own proposed mitigation was *"evaluation and refinement loop."* That is this harness's mandate, stated by the team itself — not a QA-invented opportunity to pitch.

## This task is currently BLOCKED — do not start building yet

Two open items from the same meeting/day must be answered first, because they change what this task actually builds:

1. **The RAG-vs-prompt-merging conflict** (`CLAUDE.md`'s PENDING REPLY section). If grounding genuinely changed to semantic-search/RAG-style retrieval, the "verify references" node's inputs and the whole faithfulness/non-contradiction framing may look different than assumed.
2. **What "verify references" mechanically does today.** The meeting claimed "no fabricated citations — every source verified against live references before drafting begins," but didn't specify whether that means real citation verification (author/title/journal/year confirmed to exist and match, Editorial's current standard) or a lighter check (URL resolves, format matches). This task cannot be scoped correctly without knowing which.

**Do not guess at either of these to make progress.** Flag them and wait, or scope only the parts of this task that don't depend on the answer (see below).

## What can be scoped now, without those answers

- **Where in the pipeline a quality gate would attach.** The two most likely attachment points, regardless of how the open questions resolve: (a) after "draft article," before "assemble output" — catching structural/faithfulness issues before final assembly; (b) as a check on "verify references" itself — confirming the verification step's own output meets a bar, not just trusting it. Both are worth scoping as candidate designs; don't commit to one yet.
- **Which existing checks are attachment-ready today, format-wise.** Since pipeline output is confirmed Markdown (not docx), the Tier 1 checks that are already format-agnostic (teaching-case standard, references format, arrow style, abbreviation footnotes, density/redundancy) are more directly reusable here than anything docx-specific. Worth an explicit inventory of which of the 7 Tier 1 checks apply cleanly to markdown output vs. which assumed docx structure.
- **The question-article-linkage testing gap.** The meeting revealed articles are associated with specific questions in Payload (a student missing a question can be linked to a related article) — this is a distinct, unscoped testing surface (is the article correctly linked to the right question, not just is the article itself good). Worth a short design note flagging this as future scope, even if this task doesn't build it — don't let it get lost.
- **The prompt-change-as-eval-trigger question.** Since authoring instructions now live in S3 and are Editorial-managed rather than hardcoded, worth a scoping note (not a build) on whether an S3 prompt change should trigger the same kind of re-baseline run a model-version bump would. This connects to but is distinct from the existing CI-trigger design in the Tier 1 task.

## What this task does NOT include yet

- Actually wiring any check into the live pipeline — blocked on the two open items above.
- Deciding the attachment point — scope both candidates, don't commit.
- Building the question-article-linkage check — flag only, future task.
- Resolving the RAG-vs-prompt-merging conflict or the reference-verification-mechanism question — those need a human answer, not an engineering decision.

## When done (scoping pass only)

Summarize: the two candidate attachment points with tradeoffs, which of the 7 Tier 1 checks are markdown-output-ready today vs. which assumed docx, the question-article-linkage gap flagged as future scope, and the prompt-change-as-trigger question flagged as a scoping note. Do not report "built" on anything — this pass produces a design, not code, until the two blocking items are answered.
