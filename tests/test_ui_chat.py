from integration_catalogue.ui.chat import EXAMPLE_QUESTIONS, pending_query_response


def test_examples_cover_discovery_questions() -> None:
    assert any("SAP" in question for question in EXAMPLE_QUESTIONS)
    assert any("objects" in question for question in EXAMPLE_QUESTIONS)


def test_placeholder_makes_non_execution_explicit() -> None:
    response = pending_query_response("Show all applications")

    assert "not executed" in response
    assert "Show all applications" in response
