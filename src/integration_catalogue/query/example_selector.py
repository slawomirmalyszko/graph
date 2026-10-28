"""Deterministically select relevant reviewed examples for one question."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Any

DEFAULT_MAX_EXAMPLES = 5
MIN_RELEVANCE_SCORE = 6.0

_FOUNDATIONAL_QUESTIONS = {
    "How many applications are there?",
    "Show integrations carrying Orders.",
}

_FALLBACK_QUESTIONS = (
    "How many applications are there?",
    "Show integrations carrying Orders.",
    "Display all applications with more than three interfaces.",
    "Show the full path between Salesforce CRM and SAP S/4HANA.",
    (
        "Show end-to-end flows that carry the HR Employee Record, including objects "
        "in the graph, but exclude Oracle."
    ),
)

_ALIASES: dict[str, tuple[str, ...]] = {
    "Display all applications with more than three interfaces.": (
        "显示所有具有三个以上接口的应用程序。",
        "applications exposing or using the most interfaces",
    ),
    "For each interface type, show its usage count and the interface names.": (
        "which interface types are used most often",
    ),
    "Show integrations carrying Orders.": (
        "objects carried by integrations",
        "unique information objects carried by integrations",
    ),
    "Show end-to-end flows that carry the HR Employee Record.": (
        "applications with employee record in their integrations",
        "flows carrying employee information objects",
    ),
    "Show the full path between Salesforce CRM and SAP S/4HANA.": (
        "path between two applications",
    ),
}

_WORD = re.compile(r"\w+", re.UNICODE)
_STOP_WORDS = {
    "all",
    "and",
    "are",
    "between",
    "each",
    "for",
    "from",
    "have",
    "in",
    "into",
    "its",
    "of",
    "show",
    "that",
    "the",
    "their",
    "to",
    "with",
}


def _normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        character for character in folded if not unicodedata.combining(character)
    )
    return " ".join(_WORD.findall(without_marks))


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _normalize(value).split()
        if len(token) > 2 and token not in _STOP_WORDS
    }


def _similarity(question: str, candidate: str) -> float:
    normalized_question = _normalize(question)
    normalized_candidate = _normalize(candidate)
    if normalized_question == normalized_candidate:
        return 1_000.0

    question_tokens = _tokens(question)
    candidate_tokens = _tokens(candidate)
    overlap = question_tokens & candidate_tokens
    union = question_tokens | candidate_tokens
    jaccard = len(overlap) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, normalized_question, normalized_candidate).ratio()
    return len(overlap) * 4.0 + jaccard * 8.0 + sequence * 5.0


def _example_score(question: str, example: dict[str, Any]) -> float:
    example_question = str(example["question"])
    candidates = (example_question, *_ALIASES.get(example_question, ()))
    return max(_similarity(question, candidate) for candidate in candidates)


def select_examples(
    question: str,
    examples: Sequence[dict[str, Any]],
    *,
    maximum: int = DEFAULT_MAX_EXAMPLES,
) -> tuple[dict[str, Any], ...]:
    """Return foundational and highest-scoring reviewed examples in source order."""
    if not question.strip():
        raise ValueError("Question cannot be empty.")
    if maximum < 1:
        raise ValueError("maximum must be at least one.")

    scores = [(_example_score(question, example), index) for index, example in enumerate(examples)]
    if scores and max(score for score, _ in scores) < MIN_RELEVANCE_SCORE:
        fallback = set(_FALLBACK_QUESTIONS[:maximum])
        return tuple(example for example in examples if example["question"] in fallback)

    foundations = [
        index
        for index, example in enumerate(examples)
        if example["question"] in _FOUNDATIONAL_QUESTIONS
    ][:maximum]
    remaining_slots = maximum - len(foundations)
    ranked = sorted(
        (
            (score, index)
            for score, index in scores
            if index not in foundations
        ),
        key=lambda item: (-item[0], item[1]),
    )
    selected_indexes = set(foundations)
    selected_indexes.update(index for _, index in ranked[:remaining_slots])
    return tuple(
        example for index, example in enumerate(examples) if index in selected_indexes
    )
