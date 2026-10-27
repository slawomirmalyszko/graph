"""Chat content and query workflow independent of Streamlit rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from integration_catalogue.query.generator import CypherGenerator
from integration_catalogue.query.pipeline import QueryOutcome, run_question

EXAMPLE_QUESTIONS = (
    "How many applications are there?",
    "Show all objects carried by integrations.",
    "Show all end-to-end flows that interface with SAP.",
    "Show the full path between Salesforce CRM and SAP S/4HANA.",
)


@dataclass(frozen=True)
class ChatResponse:
    summary: str
    cypher: str | None = None
    parameters: dict[str, Any] | None = None
    rows: list[dict[str, Any]] | None = None
    clarification: str | None = None
    model_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int | None = None
    error: str | None = None


def _to_chat_response(outcome: QueryOutcome) -> ChatResponse:
    generated = outcome.generated
    return ChatResponse(
        summary=generated.summary,
        cypher=generated.cypher,
        parameters=generated.parameters,
        rows=outcome.rows,
        clarification=generated.clarification,
        model_id=generated.model_id,
        input_tokens=generated.input_tokens,
        output_tokens=generated.output_tokens,
        total_tokens=generated.total_tokens,
        latency_ms=generated.latency_ms,
    )


def process_question(
    generator: CypherGenerator,
    driver: Any,
    question: str,
    *,
    database: str | None = None,
) -> ChatResponse:
    """Run one question and translate expected failures into a UI-safe response."""
    try:
        return _to_chat_response(run_question(generator, driver, question, database=database))
    except Exception as error:
        return ChatResponse(
            summary="The question could not be completed.",
            error=f"{type(error).__name__}: {error}",
        )
