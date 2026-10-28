"""Canonical graph context and worked examples for NL-to-Cypher prompts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

from integration_catalogue.query.example_selector import (
    DEFAULT_MAX_EXAMPLES,
    select_examples,
)

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
        "question": "List all catalogue nodes.",
        "response": {
            "cypher": (
                "MATCH (node) UNWIND labels(node) AS node_label "
                "RETURN DISTINCT node_label ORDER BY node_label LIMIT $limit"
            ),
            "parameters": {"limit": 100},
            "summary": "List the distinct node labels present in the catalogue.",
            "confidence": 0.98,
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
    {
        "question": "Display all applications with more than three interfaces.",
        "response": {
            "cypher": (
                "MATCH (app:Application)-[:EXPOSES|USES]->(interface:Interface) "
                "WITH app, count(DISTINCT interface) AS interface_count "
                "WHERE interface_count > $minimum_interface_count "
                "RETURN app.id AS id, app.apm_id AS apm_id, app.name AS name, "
                "app.status AS status, interface_count "
                "ORDER BY interface_count DESC, name LIMIT $limit"
            ),
            "parameters": {"minimum_interface_count": 3, "limit": 100},
            "summary": (
                "Find applications with more than three interfaces and return each count."
            ),
            "confidence": 0.98,
            "clarification": None,
        },
    },
    {
        "question": "Show all integration flows and their hop count.",
        "response": {
            "cypher": (
                "MATCH path=(source:Application)-"
                "[:EXPOSES|USES|SOURCE_OF|TARGETS*1..12]-(target:Application) "
                "WHERE source.id < target.id "
                "WITH path, source, target, "
                "size([node IN nodes(path) WHERE node:Integration]) AS hop_count "
                "WHERE hop_count > 0 "
                "RETURN path, source.name AS source_application, "
                "target.name AS target_application, hop_count "
                "ORDER BY hop_count, source_application, target_application LIMIT $limit"
            ),
            "parameters": {"limit": 100},
            "summary": "Find application-to-application paths and count integration hops.",
            "confidence": 0.98,
            "clarification": None,
        },
    },
    {
        "question": (
            "For each interface type, show its usage count and the interface names."
        ),
        "response": {
            "cypher": (
                "MATCH (interface:Interface) "
                "WITH interface.interface_type AS interface_type, "
                "count(interface) AS usage_count, "
                "collect(interface.name) AS interface_names "
                "RETURN interface_type, usage_count, interface_names "
                "ORDER BY usage_count DESC, interface_type LIMIT $limit"
            ),
            "parameters": {"limit": 100},
            "summary": "Count interfaces by type and list the interfaces in each type.",
            "confidence": 0.98,
            "clarification": None,
        },
    },
    {
        "question": "Show end-to-end flows that carry the HR Employee Record.",
        "response": {
            "cypher": (
                "MATCH (integration:Integration)-[:CARRIES]->"
                "(object:InformationObject) "
                "WHERE toLower(object.name) = toLower($object_name) "
                "MATCH path=(source:Application)-"
                "[:EXPOSES|USES|SOURCE_OF|TARGETS*1..12]-(target:Application) "
                "WHERE source.id < target.id AND integration IN nodes(path) "
                "RETURN DISTINCT path LIMIT $limit"
            ),
            "parameters": {"object_name": "HR Employee Record", "limit": 50},
            "summary": (
                "Find application-to-application paths containing an integration that "
                "carries the HR Employee Record."
            ),
            "confidence": 0.98,
            "clarification": None,
        },
    },
    {
        "question": "Which applications are both a source and a target?",
        "response": {
            "cypher": (
                "MATCH (app:Application)-[:EXPOSES]->(:Interface)-[:SOURCE_OF]->"
                "(:Integration) "
                "MATCH (app)-[:USES]->(:Interface)<-[:TARGETS]-(:Integration) "
                "RETURN DISTINCT app.id AS id, app.apm_id AS apm_id, "
                "app.name AS name, app.status AS status "
                "ORDER BY name LIMIT $limit"
            ),
            "parameters": {"limit": 100},
            "summary": "Find applications participating in both outbound and inbound flows.",
            "confidence": 0.98,
            "clarification": None,
        },
    },
    {
        "question": "Show all flows with their source and target applications.",
        "response": {
            "cypher": (
                "MATCH path=(source:Application)-"
                "[:EXPOSES|USES|SOURCE_OF|TARGETS*1..12]-(target:Application) "
                "WHERE source.id < target.id "
                "AND size([node IN nodes(path) WHERE node:Integration]) > 0 "
                "RETURN path, source.name AS source_application, "
                "target.name AS target_application LIMIT $limit"
            ),
            "parameters": {"limit": 100},
            "summary": "Find each application-to-application flow once.",
            "confidence": 0.98,
            "clarification": None,
        },
    },
    {
        "question": (
            "Show end-to-end flows that carry the HR Employee Record, including objects "
            "in the graph."
        ),
        "response": {
            "cypher": (
                "MATCH (integration:Integration)-[carries:CARRIES]->"
                "(object:InformationObject) "
                "WHERE toLower(object.name) = toLower($object_name) "
                "MATCH path=(source:Application)-"
                "[:EXPOSES|USES|SOURCE_OF|TARGETS*1..12]-(target:Application) "
                "WHERE source.id < target.id AND integration IN nodes(path) "
                "RETURN path, collect(DISTINCT integration) AS integrations, "
                "collect(DISTINCT carries) AS carries_relationships, object LIMIT $limit"
            ),
            "parameters": {"object_name": "HR Employee Record", "limit": 50},
            "summary": (
                "Find HR Employee Record paths and include the object and CARRIES edges "
                "in the graph result."
            ),
            "confidence": 0.98,
            "clarification": None,
        },
    },
    {
        "question": (
            "Show end-to-end flows that carry the HR Employee Record, including objects "
            "in the graph, but exclude Oracle."
        ),
        "response": {
            "cypher": (
                "MATCH (integration:Integration)-[carries:CARRIES]->"
                "(object:InformationObject) "
                "WHERE toLower(object.name) = toLower($object_name) "
                "MATCH path=(source:Application)-"
                "[:EXPOSES|USES|SOURCE_OF|TARGETS*1..12]-(target:Application) "
                "WHERE source.id < target.id AND integration IN nodes(path) "
                "AND none(node IN nodes(path) WHERE "
                "toLower(coalesce(node.name, $empty_name)) "
                "CONTAINS toLower($excluded_name)) "
                "RETURN path, collect(DISTINCT integration) AS integrations, "
                "collect(DISTINCT carries) AS carries_relationships, object LIMIT $limit"
            ),
            "parameters": {
                "object_name": "HR Employee Record",
                "excluded_name": "Oracle",
                "empty_name": "",
                "limit": 50,
            },
            "summary": (
                "Find HR Employee Record paths with graph objects while excluding every "
                "path containing Oracle."
            ),
            "confidence": 0.98,
            "clarification": None,
        },
    },
    {
        "question": "show full path between Sforce SRM and SAo S/ANA",
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
            "summary": "Resolve misspelled application names and find their shortest path.",
            "confidence": 0.9,
            "clarification": None,
        },
    },
    {
        "question": "Enumera las cinco interfaces utilizadas por más integraciones.",
        "response": {
            "cypher": (
                "MATCH (interface:Interface)-[:SOURCE_OF|TARGETS]-"
                "(integration:Integration) "
                "WITH interface, count(DISTINCT integration) AS integration_count "
                "RETURN interface.id AS id, interface.name AS name, integration_count "
                "ORDER BY integration_count DESC, name LIMIT $limit"
            ),
            "parameters": {"limit": 5},
            "summary": "List the five interfaces used by the most integrations.",
            "confidence": 0.98,
            "clarification": None,
        },
    },
)


def load_catalogue_schema(path: Path | None = None) -> dict[str, Any]:
    """Load the Git-controlled canonical catalogue schema."""
    schema_path = path or Path(os.getenv("CATALOGUE_SCHEMA_PATH", DEFAULT_SCHEMA_PATH))
    with schema_path.open(encoding="utf-8") as schema_file:
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


def build_examples_context(
    question: str | None = None,
    *,
    maximum: int = DEFAULT_MAX_EXAMPLES,
) -> str:
    """Render all examples for inspection or a relevant subset for one question."""
    examples = EXAMPLES if question is None else select_examples(
        question,
        EXAMPLES,
        maximum=maximum,
    )
    return json.dumps(examples, indent=2, sort_keys=True)
