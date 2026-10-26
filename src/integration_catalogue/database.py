"""Read-only AuraDB connection and catalogue summary queries."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


class AuraConfigurationError(ValueError):
    """Raised when local AuraDB connection settings are missing or unsafe."""


@dataclass(frozen=True)
class AuraSettings:
    uri: str
    username: str
    password: str
    database: str | None = None

    @classmethod
    def from_environment(cls) -> AuraSettings:
        names = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
        values = {name: os.getenv(name, "").strip() for name in names}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise AuraConfigurationError(
                "Missing AuraDB settings: " + ", ".join(sorted(missing))
            )

        uri = values["NEO4J_URI"]
        if not uri.startswith("neo4j+s://"):
            raise AuraConfigurationError(
                "NEO4J_URI must use AuraDB's encrypted neo4j+s:// scheme."
            )

        return cls(
            uri=uri,
            username=values["NEO4J_USERNAME"],
            password=values["NEO4J_PASSWORD"],
            database=os.getenv("NEO4J_DATABASE", "").strip() or None,
        )


@dataclass(frozen=True)
class CatalogueSummary:
    applications: int
    interfaces: int
    integrations: int
    information_objects: int
    relationships: int

    @property
    def nodes(self) -> int:
        return (
            self.applications
            + self.interfaces
            + self.integrations
            + self.information_objects
        )


def create_driver(settings: AuraSettings) -> Any:
    """Create an AuraDB driver without exposing credentials to the UI."""
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        settings.uri,
        auth=(settings.username, settings.password),
        connection_timeout=10,
    )


def verify_and_summarize(driver: Any, database: str | None = None) -> CatalogueSummary:
    """Verify AuraDB connectivity and execute fixed read-only summary queries."""
    from neo4j import READ_ACCESS

    labels = ["Application", "Interface", "Integration", "InformationObject"]
    driver.verify_connectivity()
    session_options: dict[str, Any] = {"default_access_mode": READ_ACCESS}
    if database:
        session_options["database"] = database

    def read_summary(transaction: Any) -> CatalogueSummary:
        rows = transaction.run(
            """
            MATCH (node)
            WHERE any(label IN labels(node) WHERE label IN $labels)
            UNWIND labels(node) AS label
            WITH label, count(*) AS count
            WHERE label IN $labels
            RETURN label, count
            """,
            labels=labels,
        )
        counts = {row["label"]: row["count"] for row in rows}
        relationship_row = transaction.run(
            "MATCH ()-[relationship]->() RETURN count(relationship) AS count"
        ).single(strict=True)
        return CatalogueSummary(
            applications=counts.get("Application", 0),
            interfaces=counts.get("Interface", 0),
            integrations=counts.get("Integration", 0),
            information_objects=counts.get("InformationObject", 0),
            relationships=relationship_row["count"],
        )

    with driver.session(**session_options) as session:
        return session.execute_read(read_summary)
