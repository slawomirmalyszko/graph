"""Deterministic offline NL-to-Cypher generator for local development."""

from __future__ import annotations

from integration_catalogue.query.generator import GeneratedQuery

MOCK_MODEL_ID = "mock:reviewed-examples"


def _query(
    cypher: str,
    parameters: dict,
    summary: str,
    confidence: float = 1.0,
) -> GeneratedQuery:
    return GeneratedQuery(
        cypher=cypher,
        parameters=parameters,
        summary=summary,
        confidence=confidence,
        clarification=None,
        model_id=MOCK_MODEL_ID,
    )


RESPONSES = {
    "how many applications are there?": _query(
        "MATCH (app:Application) RETURN count(app) AS application_count",
        {},
        "Count all applications in the catalogue.",
    ),
    "show all objects carried by integrations.": _query(
        "MATCH (integration:Integration)-[:CARRIES]->(object:InformationObject) "
        "RETURN DISTINCT object.id AS id, object.name AS name, object.domain AS domain "
        "ORDER BY name LIMIT $limit",
        {"limit": 100},
        "List information objects explicitly carried by integrations.",
    ),
    "show all end-to-end flows that interface with sap.": _query(
        "MATCH path=(sap:Application)-[:EXPOSES|USES|SOURCE_OF|TARGETS*1..12]-"
        "(other:Application) "
        "WHERE toLower(sap.name) CONTAINS toLower($application_name) AND sap <> other "
        "RETURN path LIMIT $limit",
        {"application_name": "SAP", "limit": 50},
        "Find catalogue paths connecting SAP applications to other applications.",
        0.9,
    ),
    "show the full path between salesforce crm and sap s/4hana.": _query(
        "MATCH (source:Application), (target:Application) "
        "WHERE toLower(source.name) = toLower($source_name) "
        "AND toLower(target.name) = toLower($target_name) "
        "MATCH path=shortestPath((source)-[:EXPOSES|USES|SOURCE_OF|TARGETS*1..20]-"
        "(target)) RETURN path LIMIT $limit",
        {"source_name": "Salesforce CRM", "target_name": "SAP S/4HANA", "limit": 10},
        "Find the shortest catalogue path between Salesforce CRM and SAP S/4HANA.",
        0.95,
    ),
}


class MockCypherGenerator:
    """Return reviewed queries for examples and clarify every other question."""

    def generate(self, question: str) -> GeneratedQuery:
        normalized = " ".join(question.strip().lower().split())
        if not normalized:
            raise ValueError("Question cannot be empty.")
        response = RESPONSES.get(normalized)
        if response is not None:
            return response
        return GeneratedQuery(
            cypher=None,
            parameters={},
            summary="Offline mode only supports reviewed example questions.",
            confidence=0.0,
            clarification="Please choose one of the example questions or enable Bedrock mode.",
            model_id=MOCK_MODEL_ID,
        )
