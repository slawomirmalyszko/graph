"""Question-to-results orchestration shared by Streamlit and tests."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from integration_catalogue.query.bedrock import (
    BedrockSettings,
    BedrockTextAdapter,
    create_bedrock_runtime_client,
)
from integration_catalogue.query.executor import execute_read_query
from integration_catalogue.query.generator import (
    BedrockCypherGenerator,
    CypherGenerator,
    GeneratedQuery,
)
from integration_catalogue.query.mock import MockCypherGenerator
from integration_catalogue.query.safety import validate_read_only_cypher

QUERY_MODES = {"mock", "bedrock"}


class QueryModeError(ValueError):
    """Raised when query-generation mode is unsupported."""


@dataclass(frozen=True)
class QueryOutcome:
    generated: GeneratedQuery
    rows: list[dict[str, Any]] | None


def query_mode_from_environment() -> str:
    mode = os.getenv("QUERY_MODE", "mock").strip().lower()
    if mode not in QUERY_MODES:
        raise QueryModeError("QUERY_MODE must be either mock or bedrock.")
    return mode


def create_query_generator(mode: str) -> CypherGenerator:
    if mode == "mock":
        return MockCypherGenerator()
    if mode == "bedrock":
        settings = BedrockSettings.from_environment()
        client = create_bedrock_runtime_client(settings)
        return BedrockCypherGenerator(BedrockTextAdapter(client, settings))
    raise QueryModeError("Query mode must be either mock or bedrock.")


def run_question(
    generator: CypherGenerator,
    driver: Any,
    question: str,
    *,
    database: str | None = None,
) -> QueryOutcome:
    generated = generator.generate(question)
    if generated.requires_clarification:
        return QueryOutcome(generated=generated, rows=None)
    if generated.cypher is None:
        raise ValueError("Query generator returned neither Cypher nor clarification.")

    validated = validate_read_only_cypher(generated.cypher, generated.parameters)
    rows = execute_read_query(driver, validated, database=database)
    return QueryOutcome(generated=generated, rows=rows)
