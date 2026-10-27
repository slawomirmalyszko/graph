from __future__ import annotations

from dataclasses import dataclass

from neo4j import READ_ACCESS, Query

from integration_catalogue.query.executor import execute_read_query
from integration_catalogue.query.safety import CypherSafetyError, ValidatedQuery


@dataclass
class FakeRecord:
    values: dict

    def data(self) -> dict:
        return self.values


class FakeSession:
    def __init__(self) -> None:
        self.query: Query | None = None
        self.parameters: dict | None = None

    def run(self, query: Query, parameters: dict):
        self.query = query
        self.parameters = parameters
        return [FakeRecord({"name": "SAP S/4HANA"})]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

class FakeDriver:
    def __init__(self) -> None:
        self.options: dict | None = None
        self.active_session = FakeSession()

    def session(self, **options):
        self.options = options
        return self.active_session


def test_executes_validated_query_in_read_session_with_timeout() -> None:
    driver = FakeDriver()
    query = ValidatedQuery(
        cypher="MATCH (app:Application) RETURN app.name AS name LIMIT $limit",
        parameters={"limit": 10},
    )

    rows = execute_read_query(driver, query, database="neo4j", timeout_seconds=3)

    assert rows == [{"name": "SAP S/4HANA"}]
    assert driver.options == {"default_access_mode": READ_ACCESS, "database": "neo4j"}
    assert str(driver.active_session.query) == query.cypher
    assert driver.active_session.query.timeout == 3
    assert driver.active_session.parameters == {"limit": 10}


def test_rejects_non_positive_timeout() -> None:
    driver = FakeDriver()
    query = ValidatedQuery(cypher="RETURN count(*) AS count", parameters={})

    try:
        execute_read_query(driver, query, timeout_seconds=0)
    except ValueError as error:
        assert str(error) == "Query timeout must be positive."
    else:
        raise AssertionError("Expected a positive-timeout validation error.")


def test_revalidates_query_at_execution_boundary() -> None:
    driver = FakeDriver()
    unsafe = ValidatedQuery(cypher="MATCH (n) DELETE n", parameters={})

    try:
        execute_read_query(driver, unsafe)
    except CypherSafetyError as error:
        assert "DELETE" in str(error)
    else:
        raise AssertionError("Expected unsafe manually constructed query to be rejected.")

    assert driver.options is None
