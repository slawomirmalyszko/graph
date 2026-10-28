from __future__ import annotations

from neo4j.exceptions import Neo4jError

from integration_catalogue.query.generator import GeneratedQuery
from integration_catalogue.ui.chat import (
    EXAMPLE_QUESTIONS,
    SIDEBAR_QUESTION_GROUPS,
    process_question,
    rows_to_csv,
)


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


class RejectingSession(FakeSession):
    def run(self, _query, _parameters):
        raise Neo4jError("Invalid generated syntax")


class RejectingDriver:
    def session(self, **_options):
        return RejectingSession()


def test_examples_cover_discovery_questions() -> None:
    assert any("SAP" in question for question in EXAMPLE_QUESTIONS)
    assert any("objects" in question for question in EXAMPLE_QUESTIONS)


def test_sidebar_groups_preserve_curated_section_order() -> None:
    assert [group.title for group in SIDEBAR_QUESTION_GROUPS] == [
        "Example questions",
        "Typos are OK",
        "Bonjour!",
    ]
    assert [len(group.questions) for group in SIDEBAR_QUESTION_GROUPS] == [14, 2, 2]


def test_sidebar_examples_cover_discovery_typo_and_language_inputs() -> None:
    prompts = [
        question.prompt for group in SIDEBAR_QUESTION_GROUPS for question in group.questions
    ]
    assert any("SAP" in prompt for prompt in prompts)
    assert any("objects" in prompt for prompt in prompts)
    assert "appcations list" in prompts
    assert "Enumera las cinco interfaces utilizadas por más integraciones." in prompts
    assert "显示所有具有三个以上接口的应用程序。" in prompts


def test_multilingual_sidebar_questions_have_english_captions() -> None:
    language_group = SIDEBAR_QUESTION_GROUPS[-1]
    assert all(question.caption for question in language_group.questions)


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


def test_chat_workflow_retains_generated_cypher_after_validation_failure() -> None:
    generated = GeneratedQuery(
        cypher="MATCH (app:Application) RETURN app",
        parameters={},
        summary="List applications.",
        confidence=0.95,
        clarification=None,
        model_id="amazon.nova-lite-v1:0",
        input_tokens=120,
        output_tokens=30,
        total_tokens=150,
        latency_ms=400,
    )

    response = process_question(FakeGenerator(generated), FakeDriver(), "List applications")

    assert response.summary == "I couldn't run that generated query safely."
    assert response.error == (
        "The query was blocked by the read-only safety checks. Try rephrasing the question."
    )
    assert response.cypher == generated.cypher
    assert response.parameters == {}
    assert response.model_id == generated.model_id
    assert response.total_tokens == 150
    assert response.latency_ms == 400


def test_chat_workflow_retains_generated_cypher_after_auradb_rejection() -> None:
    generated = GeneratedQuery(
        cypher="MATCH (app:Application) RETURN app LIMIT $limit",
        parameters={"limit": 10},
        summary="List applications.",
        confidence=0.9,
        clarification=None,
        model_id="amazon.nova-lite-v1:0",
    )

    response = process_question(
        FakeGenerator(generated), RejectingDriver(), "List applications"
    )

    assert response.summary == "The catalogue could not complete the query."
    assert response.error == (
        "AuraDB rejected or could not complete the request. Please retry shortly."
    )
    assert response.cypher == generated.cypher
    assert response.parameters == {"limit": 10}


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
