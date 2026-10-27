from __future__ import annotations

import json

import pytest

from integration_catalogue.query.bedrock import BedrockGeneration
from integration_catalogue.query.generator import (
    BedrockCypherGenerator,
    GeneratedQuery,
    GeneratedQueryError,
)


class FakeTextAdapter:
    def __init__(self, text: str) -> None:
        self.text = text
        self.system_prompt: str | None = None
        self.user_prompt: str | None = None

    def generate(self, *, system_prompt: str, user_prompt: str) -> BedrockGeneration:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return BedrockGeneration(
            text=self.text,
            stop_reason="end_turn",
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            latency_ms=50,
        )


def query_response(**overrides) -> str:
    payload = {
        "cypher": "MATCH (app:Application) RETURN app LIMIT $limit",
        "parameters": {"limit": 100},
        "summary": "List applications.",
        "confidence": 0.99,
        "clarification": None,
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_generator_builds_contextual_prompt_and_parses_contract() -> None:
    adapter = FakeTextAdapter(query_response())
    generator = BedrockCypherGenerator(
        adapter,
        schema_context="SCHEMA",
        examples_context="EXAMPLES",
    )

    result = generator.generate(" Show applications. ")
    prompt = json.loads(adapter.user_prompt or "")

    assert prompt == {
        "canonical_schema": "SCHEMA",
        "reviewed_examples": "EXAMPLES",
        "question": "Show applications.",
    }
    assert "Return one JSON object" in (adapter.system_prompt or "")
    assert result.cypher == "MATCH (app:Application) RETURN app LIMIT $limit"
    assert result.parameters == {"limit": 100}
    assert not result.requires_clarification


def test_contract_accepts_clarification() -> None:
    result = GeneratedQuery.from_json(
        query_response(
            cypher=None,
            parameters={},
            summary="The requested application is ambiguous.",
            confidence=0.4,
            clarification="Which SAP application do you mean?",
        )
    )

    assert result.requires_clarification
    assert result.cypher is None


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("not json", "valid JSON"),
        (query_response(extra="field"), "fields must be exactly"),
        (query_response(confidence=1.5), "confidence"),
        (query_response(confidence=0.4), "Low-confidence"),
        (query_response(cypher=None), "Missing clarification"),
        (
            query_response(clarification="Which application?"),
            "both Cypher and clarification",
        ),
    ],
)
def test_contract_rejects_malformed_model_output(response: str, message: str) -> None:
    with pytest.raises(GeneratedQueryError, match=message):
        GeneratedQuery.from_json(response)


def test_generator_rejects_empty_question() -> None:
    generator = BedrockCypherGenerator(
        FakeTextAdapter(query_response()),
        schema_context="SCHEMA",
        examples_context="EXAMPLES",
    )

    with pytest.raises(ValueError, match="cannot be empty"):
        generator.generate("  ")
