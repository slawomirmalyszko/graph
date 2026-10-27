"""Convert Neo4j result entities into UI-independent graph data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neo4j.graph import Node, Path, Relationship

CANONICAL_LABELS = ("Application", "Interface", "Integration", "InformationObject")
PATH_START_X = 60
PATH_GAP_X = 135
PATH_START_Y = 260
PATH_GAP_Y = 200


@dataclass(frozen=True)
class ResultNode:
    id: str
    label: str
    kind: str
    properties: dict[str, Any] = field(default_factory=dict)
    x: int | None = None
    y: int | None = None


@dataclass(frozen=True)
class ResultEdge:
    id: str
    source: str
    target: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResultGraph:
    nodes: tuple[ResultNode, ...]
    edges: tuple[ResultEdge, ...]
    layout: str = "graph"


def _node_id(node: Node) -> str:
    return str(node.get("id") or node.element_id)


def _node_kind(node: Node) -> str:
    return next((label for label in CANONICAL_LABELS if label in node.labels), "Unknown")


def _node_label(node: Node) -> str:
    return str(node.get("name") or node.get("apm_id") or _node_id(node))


def build_result_graph(records: list[dict[str, Any]]) -> ResultGraph | None:
    """Extract real Neo4j graph entities recursively from result records."""
    nodes: dict[str, ResultNode] = {}
    edges: dict[str, ResultEdge] = {}
    contains_path = False
    path_index = 0

    def add_node(node: Node, *, x: int | None = None, y: int | None = None) -> str:
        identifier = _node_id(node)
        nodes.setdefault(
            identifier,
            ResultNode(
                id=identifier,
                label=_node_label(node),
                kind=_node_kind(node),
                properties=dict(node),
                x=x,
                y=y,
            ),
        )
        return identifier

    def add_relationship(relationship: Relationship) -> None:
        if relationship.start_node is None or relationship.end_node is None:
            return
        source = add_node(relationship.start_node)
        target = add_node(relationship.end_node)
        identifier = str(relationship.element_id)
        edges.setdefault(
            identifier,
            ResultEdge(
                id=identifier,
                source=source,
                target=target,
                label=type(relationship).__name__,
                properties=dict(relationship),
            ),
        )

    def visit(value: Any) -> None:
        nonlocal contains_path, path_index
        if isinstance(value, Path):
            contains_path = True
            for node_index, node in enumerate(value.nodes):
                add_node(
                    node,
                    x=PATH_START_X + node_index * PATH_GAP_X,
                    y=PATH_START_Y + path_index * PATH_GAP_Y,
                )
            for relationship in value.relationships:
                add_relationship(relationship)
            path_index += 1
        elif isinstance(value, Relationship):
            add_relationship(value)
        elif isinstance(value, Node):
            add_node(value)
        elif isinstance(value, dict):
            for nested in value.values():
                visit(nested)
        elif isinstance(value, (list, tuple, set)):
            for nested in value:
                visit(nested)

    for record in records:
        visit(record)

    if not nodes:
        return None
    return ResultGraph(
        nodes=tuple(nodes.values()),
        edges=tuple(edges.values()),
        layout="chain" if contains_path else "graph",
    )


def _table_value(value: Any) -> Any:
    if isinstance(value, Path):
        return " → ".join(_node_label(node) for node in value.nodes)
    if isinstance(value, Node):
        return _node_label(value)
    if isinstance(value, Relationship):
        return type(value).__name__
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(_table_value(item)) for item in value)
    if isinstance(value, dict):
        return {key: _table_value(nested) for key, nested in value.items()}
    return value


def to_table_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Make graph entities readable in Streamlit's tabular result view."""
    return [{key: _table_value(value) for key, value in record.items()} for record in records]
