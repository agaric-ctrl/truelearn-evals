"""The [UNCONFIRMED] boundary between this harness and Maestro's real Payload CMS API.

Confirmed: nothing. Maestro's real Payload API endpoint contract - base URL, auth scheme,
pagination, list-vs-single-generation response shape - has not been confirmed as of this writing;
see the root README's "Open questions" section. This module goes exactly as far as that boundary
and stops: a config surface for once the contract is confirmed, and an explicit NotImplementedError
in place of a guessed HTTP call.

mock_fetch_raw_candidates() is the offline substitute used by tests and --mock dry runs; it never
makes a network call, and its content is hand-written placeholder data, not real Maestro output.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PayloadApiConfig:
    """Every field defaults to unconfirmed, same convention as EvalConfig/SmeRoster."""

    base_url: str | None = None
    auth_token_env: str | None = None  # name of the env var holding the token, never the token itself


def load_payload_api_config(data: dict) -> PayloadApiConfig:
    return PayloadApiConfig(
        base_url=data.get("base_url"),
        auth_token_env=data.get("auth_token_env"),
    )


def fetch_raw_candidates(config: PayloadApiConfig) -> list[dict]:
    """TODO(once Maestro's Payload API endpoint/auth contract is confirmed): implement the real
    HTTP call here. Deliberately unimplemented until then, and this raises regardless of whether
    config.base_url is set - a guessed endpoint path, pagination scheme, or auth header shape could
    silently hit the wrong URL or send a malformed request against a real system, which is worse
    than refusing outright. Never call this expecting success; mock_fetch_raw_candidates() below is
    the offline substitute for exercising the rest of the ingestion pipeline.
    """

    raise NotImplementedError(
        "Maestro's real Payload API endpoint/auth contract is unconfirmed - see the root README's "
        "Open Questions. Fill in PayloadApiConfig and implement the real HTTP call here once that "
        "contract is confirmed; until then use mock_fetch_raw_candidates() for offline development "
        "and testing."
    )


def mock_fetch_raw_candidates() -> list[dict]:
    """Hand-written placeholder raw records shaped like {"payload": <GenerationPayload dict>,
    "metadata": <CandidateMetadata dict>} - NOT real Maestro output. Exists so the rest of the
    ingestion pipeline (candidates.py, ingest_batch.py) can be exercised end-to-end offline, the
    same role synthetic_cases.json plays for maestro/judge/.
    """

    return [
        {
            "payload": {
                "history": [
                    {
                        "unique_name": "Mock_Anaphylaxis_001",
                        "question_text": "<p>A 30-year-old develops hives, wheezing, and hypotension "
                                          "minutes after a bee sting.</p>",
                        "explanation_header": "<p>The correct answer is intramuscular epinephrine.</p>",
                        "explanation_footer": "<p>Reviewed 2026.</p>",
                        "main_topic": "Immunology",
                        "modifier": "Adult",
                        "question_type": "single question",
                        "question_format": "Text",
                        "references": {
                            "query": "anaphylaxis first-line treatment",
                            "results": [
                                {"url": "https://www.physio-pedia.com/anaphylaxis", "score": 0.87},
                            ],
                        },
                    },
                ],
                "chat_history": [],
            },
            "metadata": {
                "example_id": "mock-usmle-topic-000001",
                "exam_bank": "USMLE",
                "source_type": "topic",
                "input_data": {"topic": "Anaphylaxis first-line treatment"},
                "ac_ref": "AC-MOCK-1",
                "tags": ["mock"],
            },
        },
    ]
