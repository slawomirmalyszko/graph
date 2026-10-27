from __future__ import annotations

from integration_catalogue.query.generator import GeneratedQuery
from integration_catalogue.ui.chat import EXAMPLE_QUESTIONS, process_question, rows_to_csv


class FakeGenerator:
    def __init__(self, generated: GeneratedQuery) -> None:
        self.generated = generated

    def generate(self, _question: str) -> GeneratedQuery:
        return self.generated


class FailingGenerator:
    def generate(self, _question: str) -> GeneratedQuery:
        raise RuntimeError("model unavailable")


class FakeRecord:
    values = {"application_count": 16}

    def keys(self):
        return self.values.keys()

    def __getitem__(self, key):
        return self.values[key]


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def run(self, _query, _parameters):
        return [FakeRecord()]


class FakeDriver:
    def session(self, **_options):
        return FakeSession()


def test_examples_cover_discovery_questions() -> None:
    assert any("SAP" in question for question in EXAMPLE_QUESTIONS)
    assert any("objects" in question for question in EXAMPLE_QUESTIONS)


def test_chat_workflow_returns_rows_and_query_metadata() -> None:
    generated = GeneratedQuery(
        cypher="MATCH (app:Application) RETURN count(app) AS application_count",
        parameters={},
        summary="Count applications.",
        confidence=1.0,
        clarification=None,
        model_id="mock:reviewed-examples",
    )

    response = process_question(FakeGenerator(generated), FakeDriver(), "Count applications")

    assert response.rows == [{"application_count": 16}]
    assert response.cypher == generated.cypher
    assert response.model_id == "mock:reviewed-examples"
    assert response.confidence == 1.0
    assert response.error is None


def test_chat_workflow_returns_clarification_without_database_access() -> None:
    generated = GeneratedQuery(
        cypher=None,
        parameters={},
        summary="The question is ambiguous.",
        confidence=0.2,
        clarification="Which application do you mean?",
        model_id="mock:reviewed-examples",
    )

    response = process_question(FakeGenerator(generated), None, "Show its interfaces")

    assert response.clarification == "Which application do you mean?"
    assert response.rows is None


def test_chat_workflow_exposes_friendly_failure_without_fallback() -> None:
    response = process_question(FailingGenerator(), FakeDriver(), "Show applications")

    assert response.summary == "The question could not be completed."
    assert response.error == (
        "An unexpected problem occurred. Please retry or rephrase the question."
    )
    assert "model unavailable" not in response.error


def test_rows_to_csv_preserves_columns_and_serializes_nested_values() -> None:
    content = rows_to_csv(
        [
            {"name": "SAP S/4HANA", "details": {"status": "active"}},
            {"name": "Salesforce CRM", "count": 2},
        ]
    )

    assert content.splitlines()[0] == "name,details,count"
    assert "SAP S/4HANA" in content
    assert '""status"": ""active""' in content
