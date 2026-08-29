"""Data shapes for a single Maestro-generated exam question and its eval config."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GeneratedQuestion:
    """Every field defaults to empty/unset, mirroring C#'s object-initializer style where a test
    can set only the field(s) it cares about and leave the rest null."""

    unique_name: str = ""
    question_text: str = ""             # HTML, required
    explanation_header: str = ""        # HTML, required
    explanation_footer: str = ""        # HTML, required
    main_topic: str = ""
    modifier: str = ""
    question_type: str = ""
    question_format: str = ""
    references: list[str] = field(default_factory=list)
    bottom_line: str | None = None      # HTML, optional pending require_bottom_line confirmation


@dataclass
class TablePlacementConfig:
    confirmed: bool = False


@dataclass
class EvalConfig:
    """Every field defaults to "unconfirmed" - EvalConfig() with no arguments is already the
    correct all-unconfirmed default, so a check reports Skipped instead of guessing until someone
    supplies a real value here."""

    require_bottom_line: bool | None = None
    table_placement: TablePlacementConfig = field(default_factory=TablePlacementConfig)
    reference_style_pattern: str | None = None
    allowed_question_formats_by_type: dict[str, set[str]] = field(default_factory=dict)
    existing_unique_names: set[str] | None = None


def load_generated_question(data: dict) -> GeneratedQuestion:
    return GeneratedQuestion(**data)


def load_eval_config(data: dict) -> EvalConfig:
    """JSON has no set type, so a naive EvalConfig(**data) would silently hand
    existing_unique_names a list instead of a set. Build the dataclass field by field instead."""
    placement = data.get("table_placement") or {}
    return EvalConfig(
        require_bottom_line=data.get("require_bottom_line"),
        table_placement=TablePlacementConfig(confirmed=bool(placement.get("confirmed", False))),
        reference_style_pattern=data.get("reference_style_pattern"),
        allowed_question_formats_by_type={
            key: set(values)
            for key, values in (data.get("allowed_question_formats_by_type") or {}).items()
        },
        existing_unique_names=(
            set(data["existing_unique_names"])
            if data.get("existing_unique_names") is not None
            else None
        ),
    )
