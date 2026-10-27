from integration_catalogue.query.mock import MOCK_MODEL_ID, MockCypherGenerator
from integration_catalogue.query.safety import validate_read_only_cypher
from integration_catalogue.ui.chat import EXAMPLE_QUESTIONS


def test_all_reviewed_examples_have_safe_mock_queries() -> None:
    generator = MockCypherGenerator()

    for question in EXAMPLE_QUESTIONS:
        generated = generator.generate(question)
        assert generated.cypher is not None
        validate_read_only_cypher(generated.cypher, generated.parameters)
        assert generated.model_id == MOCK_MODEL_ID


def test_unknown_question_requests_clarification() -> None:
    generated = MockCypherGenerator().generate("Invent a completely different query")

    assert generated.requires_clarification
    assert generated.cypher is None
