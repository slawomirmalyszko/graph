"""Validate and load the canonical catalogue seed into Neo4j AuraDB."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED_PATH = PROJECT_ROOT / "seed" / "catalogue-seed.json"
DEFAULT_CONSTRAINTS_PATH = PROJECT_ROOT / "schema" / "constraints.cypher"

CANONICAL_ID = re.compile(r"^(app|iface|integration|info-object):[a-z0-9][a-z0-9._:-]*$")
NODE_SPECIFICATIONS = {
    "Application": {
        "required": {"id", "apm_id", "name", "status"},
        "enums": {
            "status": {
                "planned",
                "active",
                "deprecated",
                "decommissioning",
                "decommissioned",
                "unknown",
            },
            "application_role": {"business_application", "integration_platform", "both"},
        },
    },
    "Interface": {
        "required": {"id", "name", "interface_type", "status"},
        "enums": {
            "status": {
                "planned",
                "active",
                "deprecated",
                "decommissioning",
                "decommissioned",
                "unknown",
            },
            "interface_type": {
                "application_endpoint",
                "api",
                "api_operation",
                "event",
                "topic",
                "queue",
                "file_endpoint",
                "service",
                "process",
                "mapping",
                "other",
            },
        },
    },
    "Integration": {
        "required": {"id", "name", "platform_apm_id", "status"},
        "enums": {
            "status": {
                "planned",
                "active",
                "deprecated",
                "decommissioning",
                "decommissioned",
                "unknown",
            }
        },
    },
    "InformationObject": {"required": {"id", "name"}, "enums": {}},
}
RELATIONSHIP_SPECIFICATIONS = {
    "EXPOSES": ("Application", "Interface"),
    "USES": ("Application", "Interface"),
    "SOURCE_OF": ("Interface", "Integration"),
    "TARGETS": ("Integration", "Interface"),
    "CARRIES": ("Integration", "InformationObject"),
}


class SeedValidationError(ValueError):
    """Raised when seed data violates the canonical graph contract."""


def read_seed(path: Path = DEFAULT_SEED_PATH) -> dict[str, Any]:
    """Read a UTF-8 JSON seed document."""
    with path.open(encoding="utf-8") as seed_file:
        return json.load(seed_file)


def validate_seed(seed: Mapping[str, Any]) -> None:
    """Validate identifiers, required fields, enums, references, and topology."""
    errors: list[str] = []
    nodes = seed.get("nodes")
    relationships = seed.get("relationships")
    if not isinstance(nodes, Mapping) or not isinstance(relationships, Mapping):
        raise SeedValidationError("Seed must contain object-valued nodes and relationships")

    unknown_labels = set(nodes) - set(NODE_SPECIFICATIONS)
    unknown_relationships = set(relationships) - set(RELATIONSHIP_SPECIFICATIONS)
    if unknown_labels:
        errors.append(f"Unknown node labels: {sorted(unknown_labels)}")
    if unknown_relationships:
        errors.append(f"Unknown relationship types: {sorted(unknown_relationships)}")

    node_by_id: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for label, specification in NODE_SPECIFICATIONS.items():
        records = nodes.get(label, [])
        if not isinstance(records, list):
            errors.append(f"nodes.{label} must be a list")
            continue
        for position, record in enumerate(records):
            context = f"nodes.{label}[{position}]"
            if not isinstance(record, Mapping):
                errors.append(f"{context} must be an object")
                continue
            missing = specification["required"] - set(record)
            if missing:
                errors.append(f"{context} missing required properties: {sorted(missing)}")
            node_id = record.get("id")
            if not isinstance(node_id, str) or not CANONICAL_ID.fullmatch(node_id):
                errors.append(f"{context}.id is not a canonical identifier: {node_id!r}")
            elif node_id in node_by_id:
                errors.append(f"Duplicate node id: {node_id}")
            else:
                node_by_id[node_id] = (label, record)
            for property_name, allowed_values in specification["enums"].items():
                value = record.get(property_name)
                if value is not None and value not in allowed_values:
                    errors.append(f"{context}.{property_name} has invalid value: {value!r}")

    apm_ids = [
        record.get("apm_id")
        for record in nodes.get("Application", [])
        if isinstance(record, Mapping)
    ]
    duplicates = sorted(apm_id for apm_id, count in Counter(apm_ids).items() if count > 1)
    if duplicates:
        errors.append(f"Duplicate Application.apm_id values: {duplicates}")

    platform_apm_ids = {
        record.get("apm_id")
        for record in nodes.get("Application", [])
        if isinstance(record, Mapping)
        and record.get("application_role", "business_application")
        in {"integration_platform", "both"}
    }
    for integration in nodes.get("Integration", []):
        if (
            isinstance(integration, Mapping)
            and integration.get("platform_apm_id") not in platform_apm_ids
        ):
            errors.append(
                f"Integration {integration.get('id')!r} references a missing or non-platform "
                f"Application.apm_id: {integration.get('platform_apm_id')!r}"
            )

    integration_sources: Counter[str] = Counter()
    integration_targets: Counter[str] = Counter()
    for relationship_type, (from_label, to_label) in RELATIONSHIP_SPECIFICATIONS.items():
        records = relationships.get(relationship_type, [])
        if not isinstance(records, list):
            errors.append(f"relationships.{relationship_type} must be a list")
            continue
        seen_pairs: set[tuple[Any, Any]] = set()
        for position, record in enumerate(records):
            context = f"relationships.{relationship_type}[{position}]"
            if not isinstance(record, Mapping):
                errors.append(f"{context} must be an object")
                continue
            from_id, to_id = record.get("from"), record.get("to")
            pair = (from_id, to_id)
            if pair in seen_pairs:
                errors.append(f"{context} duplicates relationship {pair}")
            seen_pairs.add(pair)
            if from_id not in node_by_id or node_by_id[from_id][0] != from_label:
                errors.append(f"{context}.from must reference a {from_label}: {from_id!r}")
            if to_id not in node_by_id or node_by_id[to_id][0] != to_label:
                errors.append(f"{context}.to must reference a {to_label}: {to_id!r}")
            if relationship_type == "SOURCE_OF" and isinstance(to_id, str):
                integration_sources[to_id] += 1
            if relationship_type == "TARGETS" and isinstance(from_id, str):
                integration_targets[from_id] += 1

    for integration in nodes.get("Integration", []):
        if not isinstance(integration, Mapping) or not isinstance(integration.get("id"), str):
            continue
        integration_id = integration["id"]
        source_count = integration_sources[integration_id]
        target_count = integration_targets[integration_id]
        if source_count != 1 or target_count != 1:
            errors.append(
                f"Integration {integration_id!r} must have exactly one source and target; "
                f"found {source_count} source(s), {target_count} target(s)"
            )

    if errors:
        raise SeedValidationError("Seed validation failed:\n- " + "\n- ".join(errors))


def iter_cypher_statements(cypher: str) -> Iterable[str]:
    """Yield semicolon-delimited statements after removing comment-only lines."""
    content = "\n".join(
        line for line in cypher.splitlines() if not line.lstrip().startswith("//")
    )
    for statement in content.split(";"):
        if stripped := statement.strip():
            yield stripped


def load_seed(driver: Any, seed: Mapping[str, Any], constraints_path: Path) -> None:
    """Create constraints and replace the canonical projection idempotently."""
    validate_seed(seed)
    with driver.session() as session:
        for statement in iter_cypher_statements(constraints_path.read_text(encoding="utf-8")):
            session.run(statement).consume()

        for label in NODE_SPECIFICATIONS:
            rows = seed["nodes"].get(label, [])
            if rows:
                session.run(
                    f"UNWIND $rows AS row MERGE (node:{label} {{id: row.id}}) SET node = row",
                    rows=rows,
                ).consume()

        for relationship_type, (from_label, to_label) in RELATIONSHIP_SPECIFICATIONS.items():
            rows = seed["relationships"].get(relationship_type, [])
            if rows:
                session.run(
                    f"""
                    UNWIND $rows AS row
                    MATCH (source:{from_label} {{id: row.from}})
                    MATCH (target:{to_label} {{id: row.to}})
                    MERGE (source)-[relationship:{relationship_type}]->(target)
                    SET relationship = coalesce(row.properties, {{}})
                    """,
                    rows=rows,
                ).consume()


def verify_database(driver: Any) -> dict[str, Any]:
    """Return database counts and fail if core graph invariants are violated."""
    with driver.session() as session:
        counts = session.run(
            """
            MATCH (node)
            WHERE any(label IN labels(node) WHERE label IN $labels)
            UNWIND labels(node) AS label
            WITH label, count(*) AS count
            WHERE label IN $labels
            RETURN label, count
            """,
            labels=list(NODE_SPECIFICATIONS),
        ).data()
        invalid_topology = session.run(
            """
            MATCH (integration:Integration)
            OPTIONAL MATCH (source:Interface)-[:SOURCE_OF]->(integration)
            WITH integration, count(source) AS source_count
            OPTIONAL MATCH (integration)-[:TARGETS]->(target:Interface)
            WITH integration, source_count, count(target) AS target_count
            WHERE source_count <> 1 OR target_count <> 1
            RETURN integration.id AS id, source_count, target_count
            """
        ).data()
        invalid_platforms = session.run(
            """
            MATCH (integration:Integration)
            OPTIONAL MATCH (platform:Application {apm_id: integration.platform_apm_id})
            WHERE platform IS NULL
               OR NOT platform.application_role IN ['integration_platform', 'both']
            RETURN integration.id AS id, integration.platform_apm_id AS platform_apm_id
            """
        ).data()
    if invalid_topology or invalid_platforms:
        raise RuntimeError(
            f"Database verification failed: topology={invalid_topology}, "
            f"platforms={invalid_platforms}"
        )
    return {"counts": counts, "invalid_topology": [], "invalid_platforms": []}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED_PATH)
    parser.add_argument("--constraints", type=Path, default=DEFAULT_CONSTRAINTS_PATH)
    parser.add_argument(
        "--validate-only", action="store_true", help="Validate files without connecting to AuraDB"
    )
    return parser


def main() -> int:
    """CLI entry point."""
    arguments = _build_parser().parse_args()
    seed = read_seed(arguments.seed)
    validate_seed(seed)
    if arguments.validate_only:
        print(f"Seed is valid: {arguments.seed}")
        return 0

    missing_variables = [
        name
        for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
        if not os.environ.get(name)
    ]
    if missing_variables:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing_variables)}")

    try:
        from neo4j import GraphDatabase
    except ImportError as error:
        raise SystemExit(
            "Neo4j driver is not installed; run: python -m pip install -r requirements-auradb.txt"
        ) from error

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )
    try:
        driver.verify_connectivity()
        load_seed(driver, seed, arguments.constraints)
        verification = verify_database(driver)
    finally:
        driver.close()
    print(json.dumps(verification, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

