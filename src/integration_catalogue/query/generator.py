"""Interfaces for future Bedrock-backed Cypher generation."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeneratedQuery:
    cypher: str
    explanation: str
    confidence: float


class CypherGenerator(Protocol):
    def generate(self, question: str) -> GeneratedQuery:
        """Translate a natural-language question into candidate Cypher."""
        ...
