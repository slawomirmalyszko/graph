"""Read-only AuraDB execution boundary for validated generated Cypher."""

from __future__ import annotations

from typing import Any

from integration_catalogue.query.safety import ValidatedQuery, validate_read_only_cypher

QUERY_TIMEOUT_SECONDS = 10.0


def execute_read_query(
    driver: Any,
    query: ValidatedQuery,
    *,
    database: str | None = None,
    timeout_seconds: float = QUERY_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Execute only a validated query in a Neo4j read transaction."""
    if timeout_seconds <= 0:
        raise ValueError("Query timeout must be positive.")

    query = validate_read_only_cypher(query.cypher, query.parameters)

    from neo4j import READ_ACCESS, Query

    session_options: dict[str, Any] = {"default_access_mode": READ_ACCESS}
    if database:
        session_options["database"] = database

    timed_query = Query(query.cypher, timeout=timeout_seconds)

    with driver.session(**session_options) as session:
        result = session.run(timed_query, query.parameters)
        return [record.data() for record in result]
