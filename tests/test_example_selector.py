from __future__ import annotations

import pytest

from integration_catalogue.query.context import EXAMPLES
from integration_catalogue.query.example_selector import select_examples


def selected_questions(question: str) -> set[str]:
    return {example["question"] for example in select_examples(question, EXAMPLES)}


def test_selector_always_includes_foundational_examples() -> None:
    questions = selected_questions("Find SAP interfaces used by integrations.")

    assert "How many applications are there?" in questions
    assert "Show integrations carrying Orders." in questions
    assert len(questions) == 5


def test_selector_prioritizes_exact_reviewed_question() -> None:
    question = "Show all integration flows and their hop count."

    assert question in selected_questions(question)


def test_selector_generalizes_employee_record_wording() -> None:
    questions = selected_questions(
        "Find applications that have employee record in their integrations."
    )

    assert "Show end-to-end flows that carry the HR Employee Record." in questions


def test_selector_uses_multilingual_alias() -> None:
    questions = selected_questions("显示所有具有三个以上接口的应用程序。")

    assert "Display all applications with more than three interfaces." in questions


def test_selector_uses_broad_fallback_for_unseen_language() -> None:
    selected = select_examples(
        "Mely alkalmazások rendelkeznek háromnál több interfésszel?",
        EXAMPLES,
    )

    assert tuple(example["question"] for example in selected) == (
        "How many applications are there?",
        "Show integrations carrying Orders.",
        "Show the full path between Salesforce CRM and SAP S/4HANA.",
        "Display all applications with more than three interfaces.",
        (
            "Show end-to-end flows that carry the HR Employee Record, including objects "
            "in the graph, but exclude Oracle."
        ),
    )


def test_known_multilingual_alias_does_not_use_fallback() -> None:
    questions = selected_questions("显示所有具有三个以上接口的应用程序。")

    assert "List all catalogue nodes." in questions
    assert (
        "Show end-to-end flows that carry the HR Employee Record, including objects "
        "in the graph, but exclude Oracle."
    ) not in questions


def test_selector_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="empty"):
        select_examples(" ", EXAMPLES)
    with pytest.raises(ValueError, match="at least one"):
        select_examples("applications", EXAMPLES, maximum=0)


@pytest.mark.parametrize(
    ("question", "expected_example"),
    [
        ("How many applications are there?", "How many applications are there?"),
        ("List all catalogue nodes.", "List all catalogue nodes."),
        (
            "Which applications expose or use the most interfaces?",
            "Display all applications with more than three interfaces.",
        ),
        (
            "Show all integration flows and their hop count.",
            "Show all integration flows and their hop count.",
        ),
        (
            "Which interface types are used most often?",
            "For each interface type, show its usage count and the interface names.",
        ),
        (
            "For each interface type, show its usage count and the interface names.",
            "For each interface type, show its usage count and the interface names.",
        ),
        (
            "Which applications are both a source and a target?",
            "Which applications are both a source and a target?",
        ),
        ("Show all objects carried by integrations.", "Show integrations carrying Orders."),
        (
            "Show the unique objects carried by integrations.",
            "Show integrations carrying Orders.",
        ),
        (
            "Show all flows with their source and target applications.",
            "Show all flows with their source and target applications.",
        ),
        (
            "Show end-to-end flows that carry the HR Employee Record.",
            "Show end-to-end flows that carry the HR Employee Record.",
        ),
        (
            "Show end-to-end flows that carry the HR Employee Record, including objects "
            "in the graph.",
            "Show end-to-end flows that carry the HR Employee Record, including objects "
            "in the graph.",
        ),
        (
            "Show end-to-end flows that carry the HR Employee Record, including objects "
            "in the graph, but exclude Oracle.",
            "Show end-to-end flows that carry the HR Employee Record, including objects "
            "in the graph, but exclude Oracle.",
        ),
        (
            "Show the full path between Salesforce CRM and SAP S/4HANA.",
            "Show the full path between Salesforce CRM and SAP S/4HANA.",
        ),
        ("appcations list", "Show applications containing SAP in their name."),
        (
            "show full path between Sforce SRM and SAo S/ANA",
            "show full path between Sforce SRM and SAo S/ANA",
        ),
        (
            "Enumera las cinco interfaces utilizadas por más integraciones.",
            "Enumera las cinco interfaces utilizadas por más integraciones.",
        ),
        (
            "显示所有具有三个以上接口的应用程序。",
            "Display all applications with more than three interfaces.",
        ),
    ],
)
def test_selector_routes_all_sidebar_questions(
    question: str,
    expected_example: str,
) -> None:
    assert expected_example in selected_questions(question)
