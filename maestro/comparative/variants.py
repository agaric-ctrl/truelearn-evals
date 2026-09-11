"""The "variant pair" data shape - docs/qa-context/COMPARATIVE_AB_TESTING_TASK.md point 1.

Same input, two labeled outputs, free-text label for what varied - deliberately NOT a fixed enum
of axis names (e.g. NOT `axis: Literal["single_step", "multi_step", ...]`), per the task's explicit
instruction: the list of interesting comparisons will grow (prompt-merging vs RAG, structured vs
unstructured, short vs long chat history, single-step vs multi-step, sequential vs
draft-review-rewrite, and whatever gets proposed after this), and hardcoding today's known axes
into the schema would mean a code change every time a new comparison axis is proposed. `label` is
just a string; nothing here validates or constrains its content.

DESIGN DECISION: `source` (the Tier 3 grounding/retrieval material) lives on each Variant
independently, NOT once on the pair as something shared by both sides. This matters for exactly the
highest-priority comparison this scaffold exists for: prompt-merging vs. RAG. Those two approaches
would use genuinely different grounding material by definition (one merges documents into the
prompt, one retrieves passages) - assuming a single shared `source` for both variants would be
wrong for that exact comparison, even though it happens to be correct for a same-source comparison
like "verbose vs terse phrasing of the same content" (see fixtures/hand_constructed_pair.json,
where both variants happen to share the same source material because only phrasing varies there).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from maestro.models import GeneratedQuestion, load_generated_question


@dataclass
class Variant:
    label: str  # free-text: "terse", "single-step", "prompt-merging", etc. - not an enum
    output: GeneratedQuestion
    source: list[str] = field(default_factory=list)


@dataclass
class VariantPair:
    pair_id: str
    input: dict  # whatever the generation entrypoint takes - topic/exam_bank/etc, unconstrained
    variant_a: Variant
    variant_b: Variant


def load_variant_pair(data: dict) -> VariantPair:
    return VariantPair(
        pair_id=data["pair_id"],
        input=data["input"],
        variant_a=_load_variant(data["variant_a"]),
        variant_b=_load_variant(data["variant_b"]),
    )


def _load_variant(data: dict) -> Variant:
    return Variant(
        label=data["label"],
        output=load_generated_question(data["output"]),
        source=data.get("source", []),
    )


def variant_pair_to_dict(pair: VariantPair) -> dict:
    return asdict(pair)
