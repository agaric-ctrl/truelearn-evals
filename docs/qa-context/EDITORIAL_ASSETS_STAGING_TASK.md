# Task: Stage Editorial's Existing Assets as Draft QA Test Data (Not Yet Authoritative)

**No dependency on the RAG-vs-prompt-merging question (see CLAUDE.md's PENDING REPLY section).** This task stages Editorial's existing question-bank, image-catalog, and reference-article assets and runs Tier 1 checks against real articles — none of that touches Maestro's retrieval architecture. Proceed regardless of whether that reply has landed.

Read `docs/qa-context/MAESTRO_QA_FINDINGS.md` Section 3 first — specifically the golden-dataset-ownership finding. This task is written to respect that finding, not route around it: everything produced here is a **proposal for Editorial/SME review**, not adopted golden data. If you find yourself about to wire any of this into a real gate or pipeline as if it were authoritative, stop — that's out of scope here.

## What exists to work from

Editorial's live article-generation workflow already uses three kinds of real, production assets:
- A question-bank export (JSON) — real questions with topic metadata, correct answers, explanations, and attachment/image references.
- An image catalog (JSON) — real images with pre-written descriptions, associated topics, and source question references. This is effectively a pre-labeled dataset already, not raw material.
- Three approved reference articles (docx) already used as the canonical style/structure examples in Editorial's own generation instructions.

A starting extraction script may already exist in this repo or a staging location (built in an earlier session, not yet reviewed by Editorial) — check before rebuilding from scratch. If missing, build fresh per the spec below.

**Confirmed, not assumed, as of the Step 0 check:** `maestro/golden_data/` contains exactly one file — `sme_roster.json`, with all three exam banks (USMLE/COMLEX/COMAT) showing `reviewer_id: null` and an explicit placeholder note. No `<bank>.jsonl` files exist. `import_pool.py`'s output path is caller-supplied via `--golden-dir`, not a fixed convention. **There is no existing "approved" location to stay separate from — this task needs to propose that convention, not just avoid colliding with an existing one.**

**Also confirmed:** the existing golden-data system is organized by **exam bank** (USMLE/COMLEX/COMAT — a property `import_pool.py` and `models.py`'s `GoldenExample` already key on). Editorial's assets are organized by **subject/content-area** (Biochemistry, Immunology, etc. — Editorial's own section-tag taxonomy). These are different axes: a single Biochemistry question is tagged `"Exam": "USMLE Step 1"`, meaning one subject's content can span multiple exam banks. Don't pick one axis for the directory structure and lose the other — stage by subject (since that matches how the raw source bundles arrive, one JSON+docx set per subject) and carry `exam_bank` as a field on every record, so records can later be filtered/promoted into the bank-keyed convention `import_pool.py` already expects.

**Proposed convention** (a proposal to establish now, not a description of something that already exists):

- `maestro/golden_data/approved/<bank>.jsonl` — where `import_pool.py` should be pointed via `--golden-dir maestro/golden_data/approved`, going forward. This task does not change `import_pool.py`'s code or defaults — it's a convention to invoke it with, worth flagging to whoever owns that tool rather than baking in silently.
- `maestro/golden_data/staging/<subject>/` — where this task's draft records land. Never the same path as the approved convention above; confirm no overlap before finalizing.
- `maestro/golden_data/manifests/<subject>.yaml` — one manifest per subject, recording the raw snapshot's source and version:

```yaml
subject: Biochemistry
source: "Article Generation - Biochemistry" Claude Project
snapshot_version: "<the source's own generated_on_utc or equivalent timestamp>"
storage:
  questions: s3://[bucket]/editorial-snapshots/<subject>/<subject>Questions.json
  image_catalog: s3://[bucket]/editorial-snapshots/<subject>/<subject>ImageCatalog.json
reference_articles:
  - <list of reference .docx filenames>
checksum_questions: sha256:...
```

Every staged record must carry both `subject` and `exam_bank`, plus a reference to the manifest's `snapshot_version`, so promotion later is a filter-and-move into `approved/<bank>.jsonl`, not a rewrite — and so a later content update makes stale staged data visibly out of date.

**Reuse `maestro/golden/models.py`'s existing `GoldenExample` shape and `QUESTION_SOURCE_TYPES` pattern** for these staged records rather than inventing a parallel schema — check whether `QUESTION_SOURCE_TYPES` already needs extending to cover `"article_fixture"` and `"image_selection"` as source types, or whether that's a separate small change worth calling out rather than silently working around.

**The promotion mechanism (pointing Tier 2's blind-review tool at staged proposals) is correct in principle but currently has no reviewer to execute it** — `sme_roster.json` shows every bank unassigned. This task should stage data and make it review-ready, but must say explicitly, in its own output, that promotion is blocked on SME assignment, not on anything this task itself failed to do. Don't treat "nobody's assigned yet" as a reason to skip staging — it's a reason to be honest about what happens after staging.

This data-architecture layer still doesn't require the sidecar-vs-library architecture fork to be resolved.

## The task

**1. Build/adapt an extraction script that converts these three asset types into draft, clearly-labeled records** — not final golden data:
   - Question-bank entries → draft records tagged by a proposed difficulty tier (best-in-class / known-hard / adversarial), using stratified sampling (e.g., topic diversity, presence of images, explanation length/structure as heuristics for "hard"). **Explicitly document that these heuristics are starting points needing SME confirmation, not validated difficulty labels.**
   - Image catalog entries → draft records for a **future** image-relevance check, with positive pairs (image genuinely matches its labeled topic) and deliberately-constructed negative pairs (same image, mismatched topic label) to test whether a relevance judge would correctly reject a keyword-only match. **Do not build the actual image-relevance judge in this task** — that's new Tier 3 scope, not covered by any existing task doc. Stage the data, flag the judge as future work.
   - Reference articles → decomposed atomic fixtures (one per Teaching Case, one per table, one per reference entry), not one record per whole file. Three articles should yield several dozen fixtures this way, not three.

**2. Mark every record with an explicit draft/proposal status** (e.g. a `status: draft_proposal` field or equivalent) and do not wire any of it into this repo's real golden-set import/gate pipeline. The deliverable is a reviewable proposal, not new production data.

**3. Separately — and this part is NOT gated on ownership questions — run the Tier 1 checks built in the earlier task against the actual, full reference articles (not the decomposed fixtures from step 1).** This is real validation against real, already-approved production content. Produce the same kind of human-readable report already demonstrated for this check category. Any genuine finding (e.g., a missing abbreviation footnote in an approved article) should be written up plainly as a finding to hand back to Editorial — this is a legitimate, low-risk way to demonstrate the harness's value using content that already exists and is already trusted, and it doesn't require anyone's sign-off to run.

**4. Do not overclaim what step 3 proves.** A clean or messy result on three articles is a demonstration of the checks working, not a statement about Editorial's overall content quality — say so explicitly in whatever report this produces.

## What this task does NOT include

- Building the image-relevance judge itself — flagged as future work only.
- Wiring any staged record into the real golden-set pipeline as authoritative data.
- Making any claim that this constitutes "the" golden dataset for either pipeline. Every output artifact from this task should say, plainly, that it's a proposal pending Editorial/SME review.

## CI wiring

None required. This is a one-time staging and validation exercise, not something that needs to run automatically. If useful later, the Tier 1 validation run against real articles could become one more input to the existing manual/scheduled Tier 1 report job — optional, not required to complete this task.

## Acceptance criteria

- A subject manifest exists recording the snapshot version/source for the raw data used, per the data-architecture section above.
- All draft records are clearly marked as proposals, not silently treated as adopted golden data anywhere in code or output.
- Staged records live in a `staging/` location structurally separate from wherever real approved golden data lives — not just tagged, but physically separated.
- The Tier 1 validation run against the real reference articles produces a genuine report with real findings (not a mocked or idealized result).
- The image-relevance dataset exists as staged data with an explicit note that the judge itself is unbuilt, future scope.
- Nothing in this task's output claims ownership over golden-dataset curation — every artifact frames itself as input to an Editorial/SME decision, not a QA-made decision.

## When done

Summarize: the manifest you created and what snapshot version it points to, what got staged and how it's tagged (and where, relative to the approved-data location), what the real Tier 1 run against Editorial's own approved articles actually found, and explicitly call out the image-relevance dataset as flagged-but-not-built future scope — plus a plain-language note ready to hand to Editorial along the lines of "here's a starting proposal for your review, and here's what we found just from running structural checks against your existing approved articles."
