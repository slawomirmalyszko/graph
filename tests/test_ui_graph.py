from integration_catalogue.query.result_graph import ResultEdge, ResultGraph, ResultNode
from integration_catalogue.ui.graph import NODE_STYLES, to_agraph


def test_maps_canonical_graph_to_agraph_styles() -> None:
    assert {kind: size for kind, (_, size) in NODE_STYLES.items() if kind != "Unknown"} == {
        "Application": 32,
        "Interface": 20,
        "Integration": 24,
        "InformationObject": 18,
    }
    graph = ResultGraph(
        nodes=(
            ResultNode(
                "app:sap",
                "SAP S/4HANA",
                "Application",
                {"status": "active"},
                x=0,
                y=0,
            ),
            ResultNode(
                "iface:sap",
                "Salesforce Order Outbound",
                "Interface",
                x=220,
                y=0,
            ),
        ),
        edges=(ResultEdge("rel-1", "app:sap", "iface:sap", "EXPOSES"),),
        layout="chain",
    )

    nodes, edges, config = to_agraph(graph)

    assert nodes[0].color == NODE_STYLES["Application"][0]
    assert nodes[1].color == NODE_STYLES["Interface"][0]
    assert nodes[0].size == 32
    assert nodes[1].size == 20
    assert nodes[1].label == "Salesforce Order\nOutbound"
    assert nodes[0].x == 0
    assert nodes[1].x == 220
    assert edges[0].label == "EXPOSES"
    assert config.physics["enabled"] is False
    assert config.layout["hierarchical"]["enabled"] is False
