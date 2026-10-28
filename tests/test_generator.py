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
        self.model_id = "amazon.nova-lite-v1:0"
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
    assert "case-insensitive name fragment" in (adapter.system_prompt or "")
    assert result.cypher == "MATCH (app:Application) RETURN app LIMIT $limit"
    assert result.parameters == {"limit": 100}
    assert not result.requires_clarification
    assert result.model_id == "amazon.nova-lite-v1:0"
    assert result.total_tokens == 120


def test_generator_selects_examples_for_each_question() -> None:
    adapter = FakeTextAdapter(query_response())
    generator = BedrockCypherGenerator(adapter, schema_context="SCHEMA")

    generator.generate("Show all integration flows and their hop count.")
    first_prompt = json.loads(adapter.user_prompt or "")
    generator.generate("显示所有具有三个以上接口的应用程序。")
    second_prompt = json.loads(adapter.user_prompt or "")

    assert "Show all integration flows and their hop count." in first_prompt[
        "reviewed_examples"
    ]
    assert "Display all applications with more than three interfaces." in second_prompt[
        "reviewed_examples"
    ]
    assert first_prompt["reviewed_examples"] != second_prompt["reviewed_examples"]


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


def test_contract_accepts_single_json_code_fence() -> None:
    result = GeneratedQuery.from_json(f"```json\n{query_response()}\n```")

    assert result.cypher == "MATCH (app:Application) RETURN app LIMIT $limit"


def test_contract_rejects_fenced_json_with_surrounding_commentary() -> None:
    with pytest.raises(GeneratedQueryError, match="valid JSON"):
        GeneratedQuery.from_json(f"Here is the query:\n```json\n{query_response()}\n```")


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
