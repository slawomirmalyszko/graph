"""Streamlit rendering for canonical Neo4j result graphs."""

from __future__ import annotations

import json
import textwrap

import streamlit_agraph as _streamlit_agraph
from streamlit_agraph import Config, Edge, Node

from integration_catalogue.query.result_graph import ResultGraph

NODE_STYLES = {
    "Application": ("#EAB308", 40),
    "Interface": ("#06B6D4", 25),
    "Integration": ("#F97316", 30),
    "InformationObject": ("#EC4899", 22),
    "Unknown": ("#94A3B8", 25),
}
NODE_LABEL_WIDTH = 18


def _title(kind: str, properties: dict) -> str:
    details = json.dumps(properties, indent=2, sort_keys=True, default=str)
    return f"{kind}\n{details}"


def _display_label(label: str) -> str:
    """Wrap long labels so adjacent path nodes remain readable."""
    return "\n".join(
        textwrap.wrap(
            label,
            width=NODE_LABEL_WIDTH,
            break_long_words=False,
            break_on_hyphens=False,
        )
    )


def to_agraph(graph: ResultGraph) -> tuple[list[Node], list[Edge], Config]:
    """Map UI-independent graph data to streamlit-agraph components."""
    nodes = []
    for node in graph.nodes:
        colour, size = NODE_STYLES.get(node.kind, NODE_STYLES["Unknown"])
        options = {
            "id": node.id,
            "label": _display_label(node.label),
            "title": _title(node.kind, node.properties),
            "color": colour,
            "size": size,
            "font": {"color": colour},
        }
        if node.x is not None and node.y is not None:
            options.update({"x": node.x, "y": node.y})
        nodes.append(Node(**options))

    edges = [
        Edge(
            source=edge.source,
            target=edge.target,
            label=edge.label,
            title=_title(edge.label, edge.properties),
            font={"color": "#64748B", "size": 11, "strokeWidth": 0},
        )
        for edge in graph.edges
    ]
    config = Config(
        width=1440,
        height=600 if graph.layout == "chain" else 660,
        directed=True,
        physics=graph.layout != "chain",
        hierarchical=False,
    )
    return nodes, edges, config


def render_graph(graph: ResultGraph, *, key: str) -> None:
    """Render one keyed graph, allowing multiple graph results in chat history."""
    nodes, edges, config = to_agraph(graph)
    data_json = json.dumps(
        {"nodes": [node.to_dict() for node in nodes], "edges": [edge.to_dict() for edge in edges]}
    )
    config_json = json.dumps(config.__dict__)
    _streamlit_agraph._agraph(data=data_json, config=config_json, key=key)
