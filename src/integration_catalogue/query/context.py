"""Canonical graph context and worked examples for NL-to-Cypher prompts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schema" / "catalogue-schema.yaml"

EXAMPLES: tuple[dict[str, Any], ...] = (
    {
        "question": "How many applications are there?",
        "response": {
            "cypher": "MATCH (app:Application) RETURN count(app) AS application_count",
            "parameters": {},
            "summary": "Count all applications in the catalogue.",
            "confidence": 1.0,
            "clarification": None,
        },
    },
    {
        "question": "Show applications containing SAP in their name.",
        "response": {
            "cypher": (
                "MATCH (app:Application) "
                "WHERE toLower(app.name) CONTAINS toLower($application_name) "
                "RETURN app.id AS id, app.apm_id AS apm_id, app.name AS name, "
                "app.status AS status ORDER BY name LIMIT $limit"
            ),
            "parameters": {"application_name": "SAP", "limit": 100},
            "summary": "Find applications whose names contain SAP.",
            "confidence": 0.98,
            "clarification": None,
        },
    },
    {
        "question": "Show integrations carrying Orders.",
        "response": {
            "cypher": (
                "MATCH (integration:Integration)-[:CARRIES]->(object:InformationObject) "
                "WHERE toLower(object.name) = toLower($object_name) "
                "RETURN integration.id AS integration_id, integration.name AS integration_name, "
                "object.name AS information_object ORDER BY integration_name LIMIT $limit"
            ),
            "parameters": {"object_name": "Orders", "limit": 100},
            "summary": "Find integrations explicitly related to the Orders information object.",
            "confidence": 0.95,
            "clarification": None,
        },
    },
    {
        "question": "Show all end-to-end flows that interface with SAP.",
        "response": {
            "cypher": (
                "MATCH path=(application:Application)-"
                "[:EXPOSES|USES|SOURCE_OF|TARGETS*1..12]-(other:Application) "
                "WHERE toLower(application.name) CONTAINS toLower($application_name) "
                "AND application <> other "
                "RETURN DISTINCT path LIMIT $limit"
            ),
            "parameters": {"application_name": "SAP", "limit": 50},
            "summary": "Find catalogue paths connecting SAP applications to other applications.",
            "confidence": 0.95,
            "clarification": None,
        },
    },
    {
        "question": "Show the full path between Salesforce CRM and SAP S/4HANA.",
        "response": {
            "cypher": (
                "MATCH (source:Application), (target:Application) "
                "WHERE toLower(source.name) = toLower($source_name) "
                "AND toLower(target.name) = toLower($target_name) "
                "MATCH path=shortestPath((source)-"
                "[:EXPOSES|USES|SOURCE_OF|TARGETS*1..20]-(target)) "
                "RETURN path LIMIT $limit"
            ),
            "parameters": {
                "source_name": "Salesforce CRM",
                "target_name": "SAP S/4HANA",
                "limit": 10,
            },
            "summary": "Find the shortest catalogue path between the two applications.",
            "confidence": 0.95,
            "clarification": None,
        },
    },
)


def load_catalogue_schema(path: Path = DEFAULT_SCHEMA_PATH) -> dict[str, Any]:
    """Load the Git-controlled canonical catalogue schema."""
    with path.open(encoding="utf-8") as schema_file:
        schema = yaml.safe_load(schema_file)
    if not isinstance(schema, dict):
        raise ValueError("Canonical catalogue schema must be a YAML object.")
    return schema


def build_schema_context(schema: dict[str, Any] | None = None) -> str:
    """Render the prompt-relevant canonical schema as deterministic JSON."""
    source = schema or load_catalogue_schema()
    keys = ("enums", "nodes", "relationships", "invariants")
    context = {key: source[key] for key in keys if key in source}
    return json.dumps(context, indent=2, sort_keys=True)


def build_examples_context() -> str:
    """Render reviewed natural-language-to-Cypher examples."""
    return json.dumps(EXAMPLES, indent=2, sort_keys=True)
