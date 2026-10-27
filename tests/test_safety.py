from __future__ import annotations

import pytest

from integration_catalogue.query.safety import CypherSafetyError, validate_read_only_cypher


def test_accepts_parameterized_bounded_read_query() -> None:
    validated = validate_read_only_cypher(
        "MATCH (app:Application) WHERE app.name = $name RETURN app LIMIT $limit",
        {"name": "SAP", "limit": 100},
    )

    assert validated.parameters == {"name": "SAP", "limit": 100}


def test_accepts_single_count_without_limit() -> None:
    validated = validate_read_only_cypher(
        "MATCH (app:Application) RETURN count(app) AS application_count",
        {},
    )

    assert validated.cypher.endswith("application_count")


@pytest.mark.parametrize(
    "cypher",
    [
        "MATCH (n) CREATE (:Application) RETURN n LIMIT $limit",
        "MATCH (n) INSERT (:Application) RETURN n LIMIT $limit",
        "MATCH (n) MERGE (:Application {id: $id}) RETURN n LIMIT $limit",
        "MATCH (n) DELETE n",
        "MATCH (n) SET n.name = $name RETURN n LIMIT $limit",
        "CALL db.labels() YIELD label RETURN label LIMIT $limit",
        "LOAD CSV FROM $url AS row RETURN row LIMIT $limit",
        "MATCH (n) RETURN n LIMIT $limit GRANT ROLE reader TO user",
    ],
)
def test_rejects_write_and_unsupported_clauses(cypher: str) -> None:
    with pytest.raises(CypherSafetyError, match="Unsupported Cypher clause"):
        validate_read_only_cypher(cypher, {"id": "x", "name": "x", "url": "x", "limit": 10})


def test_rejects_multiple_statements() -> None:
    with pytest.raises(CypherSafetyError, match="multiple"):
        validate_read_only_cypher("MATCH (n) RETURN n; MATCH (m) RETURN m", {})


def test_ignores_forbidden_words_inside_comments_and_identifiers() -> None:
    validated = validate_read_only_cypher(
        "MATCH (n:`CREATE`) // DELETE is documentation\nRETURN n LIMIT $limit",
        {"limit": 10},
    )

    assert validated.parameters["limit"] == 10


def test_rejects_literal_user_values() -> None:
    with pytest.raises(CypherSafetyError, match="Literal strings"):
        validate_read_only_cypher(
            "MATCH (app:Application) WHERE app.name = 'SAP' RETURN app LIMIT $limit",
            {"limit": 10},
        )


@pytest.mark.parametrize(
    ("parameters", "message"),
    [
        ({"limit": 10}, "missing: name"),
        ({"name": "SAP", "limit": 10, "extra": True}, "unused: extra"),
        ({"name": "SAP", "limit": 0}, "integer from 1"),
        ({"name": "SAP", "limit": 501}, "integer from 1"),
        ({"name": {"nested": "value"}, "limit": 10}, "Unsupported parameter"),
    ],
)
def test_rejects_unsafe_parameters(parameters: dict, message: str) -> None:
    with pytest.raises(CypherSafetyError, match=message):
        validate_read_only_cypher(
            "MATCH (app:Application) WHERE app.name = $name RETURN app LIMIT $limit",
            parameters,
        )


def test_requires_limit_for_row_queries() -> None:
    with pytest.raises(CypherSafetyError, match="parameterized LIMIT"):
        validate_read_only_cypher("MATCH (app:Application) RETURN app", {})
