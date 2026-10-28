from __future__ import annotations

import pytest

from integration_catalogue.query.generator import GeneratedQuery
from integration_catalogue.query.mock import MockCypherGenerator
from integration_catalogue.query.pipeline import (
    GeneratedQueryProcessingError,
    QueryModeError,
    create_query_generator,
    query_mode_from_environment,
    run_question,
)


class GeneratedQueryStub:
    def generate(self, _question: str) -> GeneratedQuery:
        return GeneratedQuery(
            cypher="MATCH (app:Application) RETURN app",
            parameters={},
            summary="List applications.",
            confidence=1.0,
            clarification=None,
        )


def test_query_mode_defaults_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUERY_MODE", raising=False)

    assert query_mode_from_environment() == "mock"
    assert isinstance(create_query_generator("mock"), MockCypherGenerator)


def test_query_mode_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUERY_MODE", "automatic")

    with pytest.raises(QueryModeError, match="mock or bedrock"):
        query_mode_from_environment()


def test_run_question_preserves_generated_query_when_validation_fails() -> None:
    with pytest.raises(GeneratedQueryProcessingError) as captured:
        run_question(GeneratedQueryStub(), None, "List applications")

    assert captured.value.generated.cypher == "MATCH (app:Application) RETURN app"
