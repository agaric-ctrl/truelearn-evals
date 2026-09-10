# Questions for Editorial: Tier 1 Content-Quality Thresholds

**Status: OPEN — awaiting Editorial input. Nothing below is decided; nothing below should be
treated as a confirmed rule until an Editorial owner answers it.**

## Background — why we're asking

Maestro's QA harness includes a set of automated content checks ("Tier 1") that run against every
generated question and article. Some of these checks are fully built and already running — but a
handful of them can only ever report a raw measurement (e.g. "this scores reading grade level 15")
and never a pass/fail verdict, because no one has told the system what an acceptable range or rule
actually is. This is deliberate, not a bug: rather than the engineering/QA side guessing at a
number that sounds reasonable, the system is built to stay silent on judgment calls until someone
who owns content quality gives a real answer.

That's what this document is: a list of the specific calls only Editorial can make, with enough
background on each to answer without needing to read any code. Once we have answers, they get
typed into a config file and those checks start actually enforcing the rule — no further
engineering work needed to wire it up.

If a question doesn't have a clean answer yet, "we don't know yet, treat it as unenforced for now"
is a completely fine answer — it's the same state these checks are already in today. We'd rather
have that stated explicitly than have engineering guess.

## The questions

### 1. Reading level

**What we're asking:** Should generated questions/articles target a specific reading grade level
(Flesch-Kincaid), and if so, what's the acceptable range?

**Why it matters:** Medical exam content has a real, legitimate reason to read at a graduate/
professional level, but "too dense to parse under exam time pressure" is also a real failure mode.
Right now we can measure the grade level of any content automatically and instantly — we just have
no target to compare it against.

### 2. Redundant/repetitive phrasing

**What we're asking:** How much internal repetition (a sentence restating a point an earlier
sentence already made, rather than adding new information) is acceptable before it counts as
padding?

**Why it matters:** This is meant to catch generated content that "pads" length by restating
itself rather than teaching more. We can automatically measure how much overlap exists between
sentences in a piece of content — we don't have a sense of what amount is normal versus a real
problem.

### 3. Reference/citation rules

**What we're asking, three related sub-questions:**
- Are there specific *types* of citations (e.g. textbooks vs. journal articles vs. review papers)
  that should be capped at a certain count each?
- Are there specific sources that should never be cited (non-authoritative, outdated, or otherwise
  excluded)?
- Is there a required citation format/style (e.g. a specific author-date or numbered style) that a
  reference string must follow?

**Why it matters:** We already enforce two reference rules today (3–5 references total, listed
newest-first) — those came from an earlier, confirmed conversation with the team. These three are
the parts of the same rule set that were never specified further than "some types are capped" and
"some sources are excluded," so they currently do nothing.

### 4. Where tables are allowed to sit in content

**What we're asking:** Is there a rule for valid table placement within a question or article
(e.g. must appear after the paragraph that references it, can't appear before the first mention of
its subject, etc.)?

**Why it matters:** "Tables placed in the wrong location" was flagged early on as a real failure
mode we'd seen in generated content, but no one has ever specified what "wrong location" means
precisely enough to check for it automatically. Until we have that definition, this check does
nothing.

### 5. Is "Bottom Line" actually required?

**What we're asking:** Is the "Bottom Line" field on a question mandatory, or is it genuinely
optional?

**Why it matters:** Every other core field (question text, explanation header/footer, unique name)
is already enforced as required. Bottom Line is the one field where we were never told which way
it should go, so it's currently never checked either way.

## What happens with your answers

Each answer above becomes a single, specific value in a config file our checks already know how to
read (no new engineering work required to consume it) — a number, a list of names, or a plain
yes/no. Once that value is filled in, the corresponding check starts actually passing/failing
content on it, instead of only reporting a raw measurement with no verdict.

## Separately — one thing worth flagging while we're at it (not one of the above)

Running the existing 3–5 references rule against 71 real staged individual exam questions (not
full articles) shows **all 71 failing it — every one has 0 references.** That's a different kind
of question than the ones above: the rule itself is already confirmed, but it may have been
written with full articles in mind rather than individual questions, which may not carry a
references list the same way. Worth a quick confirmation: does the 3–5 references rule apply to
individual questions too, or only to articles?

---
*For engineering reference: each question above maps to one field on `EvalConfig`
(`maestro/models.py:31`) — `readability_grade_level_range`, `max_ngram_overlap_ratio`,
`reference_citation_type_patterns` / `max_per_citation_type`, `excluded_reference_sources`,
`reference_style_pattern`, `table_placement.confirmed`, and `require_bottom_line`, respectively.
All default to unconfirmed/`None`, which is why the checks that read them currently always report
Skipped rather than a verdict.*
