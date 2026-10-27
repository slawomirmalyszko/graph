from neo4j.graph import Graph, Node, Path

from integration_catalogue.query.result_graph import build_result_graph, to_table_rows


def make_path() -> Path:
    graph = Graph()
    application = Node(
        graph,
        "node-1",
        1,
        ["Application"],
        {"id": "app:salesforce", "name": "Salesforce CRM", "apm_id": "APM_SF_001"},
    )
    interface = Node(
        graph,
        "node-2",
        2,
        ["Interface"],
        {"id": "iface:salesforce-orders", "name": "Salesforce Order Outbound"},
    )
    integration = Node(
        graph,
        "node-3",
        3,
        ["Integration"],
        {"id": "integration:orders", "name": "Order publishing"},
    )
    exposes_type = graph.relationship_type("EXPOSES")
    exposes = exposes_type(graph, "rel-1", 11, {})
    exposes._start_node = application
    exposes._end_node = interface
    source_type = graph.relationship_type("SOURCE_OF")
    source = source_type(graph, "rel-2", 12, {})
    source._start_node = interface
    source._end_node = integration
    return Path(application, exposes, source)


def test_builds_canonical_graph_from_neo4j_path() -> None:
    path = make_path()

    graph = build_result_graph([{"path": path}, {"nested": [path]}])

    assert graph is not None
    assert graph.layout == "chain"
    assert [node.id for node in graph.nodes] == [
        "app:salesforce",
        "iface:salesforce-orders",
        "integration:orders",
    ]
    assert [node.kind for node in graph.nodes] == ["Application", "Interface", "Integration"]
    assert [(node.x, node.y) for node in graph.nodes] == [(60, 260), (195, 260), (330, 260)]
    assert [(edge.source, edge.target, edge.label) for edge in graph.edges] == [
        ("app:salesforce", "iface:salesforce-orders", "EXPOSES"),
        ("iface:salesforce-orders", "integration:orders", "SOURCE_OF"),
    ]


def test_path_becomes_readable_table_value() -> None:
    rows = to_table_rows([{"path": make_path()}])

    assert rows == [
        {"path": "Salesforce CRM → Salesforce Order Outbound → Order publishing"}
    ]


def test_scalar_rows_do_not_create_graph() -> None:
    assert build_result_graph([{"name": "SAP S/4HANA", "status": "active"}]) is None
