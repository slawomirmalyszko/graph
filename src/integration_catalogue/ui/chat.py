"""Chat content and query workflow independent of Streamlit rendering."""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass
from typing import Any

from neo4j.exceptions import DriverError, Neo4jError

from integration_catalogue.query.bedrock import BedrockResponseError
from integration_catalogue.query.generator import CypherGenerator, GeneratedQueryError
from integration_catalogue.query.pipeline import QueryOutcome, run_question
from integration_catalogue.query.result_graph import ResultGraph, build_result_graph, to_table_rows
from integration_catalogue.query.safety import CypherSafetyError

LOGGER = logging.getLogger(__name__)

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
    confidence: float | None = None
    model_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int | None = None
    error: str | None = None
    graph: ResultGraph | None = None


def _to_chat_response(outcome: QueryOutcome) -> ChatResponse:
    generated = outcome.generated
    return ChatResponse(
        summary=generated.summary,
        cypher=generated.cypher,
        parameters=generated.parameters,
        rows=to_table_rows(outcome.rows) if outcome.rows is not None else None,
        clarification=generated.clarification,
        confidence=generated.confidence,
        model_id=generated.model_id,
        input_tokens=generated.input_tokens,
        output_tokens=generated.output_tokens,
        total_tokens=generated.total_tokens,
        latency_ms=generated.latency_ms,
        graph=build_result_graph(outcome.rows) if outcome.rows is not None else None,
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value


def rows_to_csv(rows: list[dict[str, Any]]) -> str:
    """Serialize normalized result rows for a user download."""
    columns = list(dict.fromkeys(key for row in rows for key in row))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_value(row.get(key)) for key in columns})
    return output.getvalue()


def _friendly_failure(error: Exception) -> tuple[str, str]:
    if isinstance(error, CypherSafetyError):
        return (
            "I couldn't run that generated query safely.",
            "The query was blocked by the read-only safety checks. Try rephrasing the question.",
        )
    if isinstance(error, (GeneratedQueryError, BedrockResponseError)):
        return (
            "I couldn't translate that question into a query.",
            "The AI response was not usable. "
            "Try a more specific description of the catalogue data.",
        )
    if isinstance(error, (Neo4jError, DriverError)):
        return (
            "The catalogue could not complete the query.",
            "AuraDB rejected or could not complete the request. Please retry shortly.",
        )
    if type(error).__module__.startswith(("boto3", "botocore")):
        return (
            "The AI query service is currently unavailable.",
            "Check the local AWS session and Bedrock access, then retry.",
        )
    return (
        "The question could not be completed.",
        "An unexpected problem occurred. Please retry or rephrase the question.",
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
        LOGGER.exception("Question processing failed with %s", type(error).__name__)
        summary, guidance = _friendly_failure(error)
        return ChatResponse(
            summary=summary,
            error=guidance,
        )
