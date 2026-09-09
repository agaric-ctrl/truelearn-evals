"""CLI: converts Editorial's real question-bank export, image catalog, and reference .docx
articles into draft, clearly-labeled records for Editorial/SME review, per
docs/qa-context/EDITORIAL_ASSETS_STAGING_TASK.md. Everything produced here is a PROPOSAL, not
adopted golden data - nothing is wired into the real golden-set import/gate pipeline.

SCHEMA DECISION, stated explicitly rather than silently invented: staged records reuse
maestro/golden/models.py's GoldenExample shape as-is - no new dataclass fields were added for
subject/status/snapshot_version/tier, since extending the real GoldenExample schema is a bigger,
more consequential change than this proposal-only task warrants. Instead, that metadata rides in
GoldenExample.tags as structured "key:value" strings (e.g. "subject:Biochemistry",
"status:draft_proposal", "snapshot_version:...", "tier:best_in_class") - the same free-form list
already used for lightweight metadata like "edge_case" in this repo's own example fixtures. Every
record's tags always include "status:draft_proposal" - the single, greppable marker that nothing
here has been reviewed or promoted.

QUESTION_SOURCE_TYPES is deliberately NOT extended to include "article_fixture"/"image_selection".
Both are new source_type values used only by this task, but golden/models.py's QUESTION_SOURCE_TYPES
specifically marks "this source_type's `expected` is GeneratedQuestion-shaped, run it through Tier 1"
(see import_pool.py's tier1_gate() and generate_pool.py's _preview()) - and neither fixture type's
`expected` is GeneratedQuestion-shaped. Adding them would make the Tier 1 gate misfire on non-question
content; leaving them out means they correctly fall through to the same "unmodeled, generic JSON
preview, no Tier 1 gate" path "article" already takes today.

TIERING/PAIRING HEURISTICS ARE UNVALIDATED STARTING POINTS, not confirmed difficulty labels - see
each function's docstring for exactly what each one checks and why it's a proxy, not a ground truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml

from maestro.golden.docx_convert import convert_docx
from maestro.golden.models import GoldenExample, dump_golden_example

# real data uses "USMLE Step 1" / "COMLEX Level 1" style values; this repo's exam_bank convention
# (see maestro/golden/sme_roster.json) uses the bare bank name. Only normalizes what's actually
# been observed in the real data - does not invent a mapping for a bank/level never seen.
_EXAM_BANK_NORMALIZE = {
    "USMLE Step 1": "USMLE", "USMLE Step 2 CK": "USMLE", "USMLE Step 3": "USMLE",
    "COMLEX Level 1": "COMLEX", "COMLEX Level 2 CE": "COMLEX", "COMLEX Level 3": "COMLEX",
}

# Per docs/qa-context/MAESTRO_QA_FINDINGS.md Section 3's proposed sizing (20-30 best-in-class,
# 10-15 known-hard, 8-10 adversarial, per exam bank/content area) - midpoints of each range.
_TIER_TARGET_SIZE = {"best_in_class": 25, "known_hard": 12, "adversarial": 9}

_STAGING_RANDOM_SEED = 20260909  # fixed, so which questions/images get sampled is reproducible


def normalize_exam_bank(raw_exam: str) -> str:
    return _EXAM_BANK_NORMALIZE.get(raw_exam, raw_exam)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _draft_tags(*, subject: str, snapshot_version: str, extra: list[str] = ()) -> list[str]:
    return [
        "status:draft_proposal", f"subject:{subject}", f"snapshot_version:{snapshot_version}",
        *extra,
    ]


# ---------------------------------------------------------------------------
# Question tiering
# ---------------------------------------------------------------------------

def tier_questions(questions: list[dict], *, seed: int = _STAGING_RANDOM_SEED) -> dict[str, list[dict]]:
    """Splits real question-bank entries into three UNVALIDATED difficulty tiers, per exam bank -
    starting points for SME confirmation, not validated difficulty labels:

    - adversarial: Explanation is empty. Not "hard for a student" - hard for THIS harness, since a
      faithfulness/coverage judge has nothing to check a claim against with no explanation at all.
      That's a genuine edge case worth having in a test set, but calling it "adversarial" in the
      strategy doc's sense (deliberately tricky) is this script's own proxy, not a confirmed label.
    - known_hard: has at least one image Attachment AND Explanation length is at or above the
      median of the remaining (non-adversarial) pool for its bank - image-dependent questions
      requiring visual interpretation, longer explanations as a rough proxy for topic complexity.
    - best_in_class: Explanation is non-empty, KeyTakeaway is non-empty, and Explanation length
      falls within the 25th-75th percentile of the remaining pool for its bank (not too sparse,
      not an outlier-length explanation) - a "typical, complete-looking" question, nothing more.

    Sampling within each tier is capped and seeded (not "every question meeting the heuristic") -
    per-bank target sizes from the findings doc's proposed sizing (20-30 / 10-15 / 8-10).
    """

    by_bank: dict[str, list[dict]] = {}
    for question in questions:
        bank = normalize_exam_bank(question.get("Exam", ""))
        by_bank.setdefault(bank, []).append(question)

    result: dict[str, list[dict]] = {"best_in_class": [], "known_hard": [], "adversarial": []}
    for bank, bank_questions in by_bank.items():
        rng = random.Random(f"{seed}:{bank}")

        adversarial_pool = [q for q in bank_questions if not (q.get("Explanation") or "").strip()]
        remaining = [q for q in bank_questions if q not in adversarial_pool]

        lengths = sorted(len(q.get("Explanation") or "") for q in remaining)
        median_length = lengths[len(lengths) // 2] if lengths else 0
        p25 = lengths[len(lengths) // 4] if lengths else 0
        p75 = lengths[(3 * len(lengths)) // 4] if lengths else 0

        known_hard_pool = [
            q for q in remaining
            if q.get("Attachments") and len(q.get("Explanation") or "") >= median_length
        ]
        known_hard_ids = {q["UniqueName"] for q in known_hard_pool}

        best_in_class_pool = [
            q for q in remaining
            if q["UniqueName"] not in known_hard_ids
            and (q.get("KeyTakeaway") or "").strip()
            and p25 <= len(q.get("Explanation") or "") <= p75
        ]

        result["adversarial"].extend(
            rng.sample(adversarial_pool, min(len(adversarial_pool), _TIER_TARGET_SIZE["adversarial"]))
        )
        result["known_hard"].extend(
            rng.sample(known_hard_pool, min(len(known_hard_pool), _TIER_TARGET_SIZE["known_hard"]))
        )
        result["best_in_class"].extend(
            rng.sample(best_in_class_pool, min(len(best_in_class_pool), _TIER_TARGET_SIZE["best_in_class"]))
        )

    return result


def build_question_draft(question: dict, *, tier: str, subject: str, snapshot_version: str) -> GoldenExample:
    """Converts one real question-bank entry into a draft GoldenExample. Field mapping choices
    that are inferred, not confirmed, and called out as such:
    - question_type is set to "single question" because every real entry has exactly one
      CorrectAnswers entry (verified across all 789 - not assumed) - matches this repo's existing
      convention for that shape.
    - question_format is set to "Image" if Attachments is non-empty, else "Text" - a guess at
      what real Maestro/Payload would call this; UNCONFIRMED against any real format enum.
    - references is left empty - the raw data has no structured reference list for a question
      (only inline URLs sometimes embedded in Explanation text), and inventing one would be
      guessing a citation that was never really given as such.
    """

    topics = question.get("Topics") or {}
    correct = (question.get("CorrectAnswers") or [{}])[0]
    explanation_parts = [part for part in (question.get("Explanation"), question.get("KeyTakeaway")) if part]

    exam_bank = normalize_exam_bank(question.get("Exam", ""))
    return GoldenExample(
        example_id=f"biochem-{question['RootId']}",
        source_type="topic",
        exam_bank=exam_bank,
        question_type="single question",
        input={"topic": f"{topics.get('MainTopic', '')}: {topics.get('TopicModifier', '')}".strip(": ")},
        expected={
            "unique_name": question.get("UniqueName", ""),
            "question_text": f"<p>{question.get('QuestionText', '')}</p>",
            "explanation_header": f"<p>The correct answer is {correct.get('Text', '')}.</p>",
            "explanation_footer": "".join(f"<p>{part}</p>" for part in explanation_parts),
            "main_topic": topics.get("MainTopic", ""),
            "modifier": topics.get("TopicModifier", ""),
            "question_type": "single question",
            "question_format": "Image" if question.get("Attachments") else "Text",
            "references": [],
        },
        tags=_draft_tags(subject=subject, snapshot_version=snapshot_version, extra=[
            f"tier:{tier}", f"root_id:{question['RootId']}",
        ]),
        ac_ref=None,
    )


# ---------------------------------------------------------------------------
# Image-relevance pairs (data only - no judge built, per the task doc)
# ---------------------------------------------------------------------------

def build_image_pairs(
    catalog: dict, *, subject: str, snapshot_version: str,
    sample_size: int = 20, seed: int = _STAGING_RANDOM_SEED,
) -> list[GoldenExample]:
    """Stages positive and constructed-negative pairs for a FUTURE image-relevance judge - the
    judge itself is explicitly out of scope for this task (see the task doc).

    Positive pair: a real image, its own real labeled topics (already written by Editorial's
    image-cataloging process, not invented here), marked relevant. Negative pair: the SAME image,
    paired with a topic list drawn from a DIFFERENT, randomly-chosen image - a deliberately
    constructed mismatch, marked not-relevant, to test whether a future judge would correctly
    reject a keyword-only match rather than rubber-stamp any topic paired with any image.
    """

    images = list(catalog.get("images", {}).items())
    described = [(url, meta) for url, meta in images if meta.get("topics")]
    rng = random.Random(seed)
    sample = rng.sample(described, min(sample_size, len(described)))

    records: list[GoldenExample] = []
    for index, (url, meta) in enumerate(sample):
        mismatch_url, mismatch_meta = rng.choice([item for item in described if item[0] != url])

        records.append(GoldenExample(
            example_id=f"biochem-image-pos-{index:03d}",
            source_type="image_selection",
            exam_bank="",  # image relevance isn't confirmed to be a per-bank concept
            question_type="",
            input={"image_url": url, "candidate_topics": meta["topics"]},
            expected={"relevant": True, "note": "real positive pairing from Editorial's own image catalog"},
            tags=_draft_tags(subject=subject, snapshot_version=snapshot_version, extra=["pair:positive"]),
        ))
        records.append(GoldenExample(
            example_id=f"biochem-image-neg-{index:03d}",
            source_type="image_selection",
            exam_bank="",
            question_type="",
            input={"image_url": url, "candidate_topics": mismatch_meta["topics"]},
            expected={"relevant": False, "note": f"constructed negative - topics borrowed from a different image ({mismatch_url})"},
            tags=_draft_tags(subject=subject, snapshot_version=snapshot_version, extra=["pair:constructed_negative"]),
        ))
    return records


# ---------------------------------------------------------------------------
# Reference-article atomic fixtures
# ---------------------------------------------------------------------------

def build_article_fixtures(article_path: Path, *, subject: str, snapshot_version: str) -> list[GoldenExample]:
    """Decomposes one reference article into atomic fixtures - one per Teaching Case, one per
    table, one per reference entry - rather than one record for the whole file, per the task doc.
    exam_bank is left empty: these articles are study content, not confirmed to be exam-bank-
    specific the way a question is."""

    article = convert_docx(article_path)
    article_slug = re.sub(r"[^a-z0-9]+", "-", article_path.stem.lower()).strip("-")
    records: list[GoldenExample] = []

    for index, case in enumerate(article.teaching_cases):
        records.append(GoldenExample(
            example_id=f"biochem-article-{article_slug}-case-{index:02d}",
            source_type="article_fixture", exam_bank="", question_type="",
            input={"article": article_path.name, "fixture_type": "teaching_case", "label": case["label"]},
            expected={"body": case["body"]},
            tags=_draft_tags(subject=subject, snapshot_version=snapshot_version, extra=["fixture_type:teaching_case"]),
        ))

    for index, table in enumerate(article.tables):
        records.append(GoldenExample(
            example_id=f"biochem-article-{article_slug}-table-{index:02d}",
            source_type="article_fixture", exam_bank="", question_type="",
            input={"article": article_path.name, "fixture_type": "table"},
            expected={"rows": table},
            tags=_draft_tags(subject=subject, snapshot_version=snapshot_version, extra=["fixture_type:table"]),
        ))

    for index, reference in enumerate(article.references):
        records.append(GoldenExample(
            example_id=f"biochem-article-{article_slug}-reference-{index:02d}",
            source_type="article_fixture", exam_bank="", question_type="",
            input={"article": article_path.name, "fixture_type": "reference"},
            expected={"text": reference},
            tags=_draft_tags(subject=subject, snapshot_version=snapshot_version, extra=["fixture_type:reference"]),
        ))

    return records


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def build_manifest(
    *, subject: str, questions_path: Path, catalog: dict, catalog_path: Path,
    reference_articles: list[Path],
) -> dict:
    return {
        "subject": subject,
        "source": catalog.get("source_file", questions_path.name),
        "snapshot_version": catalog.get("generated_on_utc") or datetime.now(timezone.utc).isoformat(),
        "storage": {
            "note": "No real S3 bucket exists for this yet - these are LOCAL repo-relative paths, "
            "not the s3:// convention the task doc's manifest template shows. Update once a real "
            "snapshot storage location is confirmed.",
            "questions": str(questions_path),
            "image_catalog": str(catalog_path),
        },
        "reference_articles": [path.name for path in reference_articles],
        "checksum_questions": sha256_of(questions_path),
        "checksum_image_catalog": sha256_of(catalog_path),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _write_records(records: list[GoldenExample], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for record in records:
        (directory / f"{record.example_id}.json").write_text(
            json.dumps(dump_golden_example(record), indent=2), encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage Editorial's real question-bank/image-catalog/reference-article assets "
        "as draft QA test data - a proposal for Editorial/SME review, not adopted golden data.",
    )
    parser.add_argument("--subject", required=True, help='e.g. "Biochemistry"')
    parser.add_argument("--questions-json", type=Path, required=True)
    parser.add_argument("--image-catalog-json", type=Path, required=True)
    parser.add_argument("--reference-articles", type=Path, nargs="+", required=True)
    parser.add_argument("--golden-data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "golden_data")
    parser.add_argument("--image-pair-sample-size", type=int, default=20)
    args = parser.parse_args()

    questions = json.loads(args.questions_json.read_text(encoding="utf-8"), strict=False)
    catalog = json.loads(args.image_catalog_json.read_text(encoding="utf-8"), strict=False)

    manifest = build_manifest(
        subject=args.subject, questions_path=args.questions_json, catalog=catalog,
        catalog_path=args.image_catalog_json, reference_articles=args.reference_articles,
    )
    snapshot_version = manifest["snapshot_version"]
    subject_slug = args.subject.lower()

    manifests_dir = args.golden_data_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifests_dir / f"{subject_slug}.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    staging_dir = args.golden_data_dir / "staging" / subject_slug
    tiers = tier_questions(questions)
    question_records = [
        build_question_draft(question, tier=tier, subject=args.subject, snapshot_version=snapshot_version)
        for tier, tier_questions_list in tiers.items()
        for question in tier_questions_list
    ]
    _write_records(question_records, staging_dir / "questions")

    image_records = build_image_pairs(
        catalog, subject=args.subject, snapshot_version=snapshot_version,
        sample_size=args.image_pair_sample_size,
    )
    _write_records(image_records, staging_dir / "image_pairs")

    article_records: list[GoldenExample] = []
    for article_path in args.reference_articles:
        article_records.extend(
            build_article_fixtures(article_path, subject=args.subject, snapshot_version=snapshot_version)
        )
    _write_records(article_records, staging_dir / "article_fixtures")

    print(f"Wrote manifest: {manifest_path}")
    print(f"Staged {len(question_records)} question draft(s): "
          f"{ {tier: len(items) for tier, items in tiers.items()} }")
    print(f"Staged {len(image_records)} image-relevance pair(s) ({len(image_records)//2} positive/negative pairs)")
    print(f"Staged {len(article_records)} article fixture(s) from {len(args.reference_articles)} article(s)")
    print()
    print("PROMOTION IS BLOCKED ON SME ASSIGNMENT, not on anything this script failed to do: "
          "maestro/golden_data/sme_roster.json shows every exam bank (USMLE/COMLEX/COMAT) with "
          "reviewer_id: null. Nothing staged here can be reviewed by Tier 2's blind-pool mechanism "
          "until a real SME is assigned - these files are a proposal for Editorial to review "
          "directly, not yet something the existing review-pool tooling can route anywhere.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
