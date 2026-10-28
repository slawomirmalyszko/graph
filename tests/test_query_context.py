import json

from integration_catalogue.query.context import (
    build_examples_context,
    build_schema_context,
    load_catalogue_schema,
)


def test_schema_path_can_be_overridden_for_packaged_runtime(
    monkeypatch, tmp_path
) -> None:
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text("nodes: {}\n", encoding="utf-8")
    monkeypatch.setenv("CATALOGUE_SCHEMA_PATH", str(schema_path))

    assert load_catalogue_schema() == {"nodes": {}}


def test_schema_context_comes_from_canonical_schema() -> None:
    schema = load_catalogue_schema()
    context = build_schema_context(schema)

    assert '"Application"' in context
    assert '"SOURCE_OF"' in context
    assert '"connectivity_from_relationships"' in context
    assert schema["nodes"]["Integration"]["required_properties"]["platform_apm_id"]


def test_examples_use_parameters_and_canonical_graph_elements() -> None:
    examples = build_examples_context()

    assert "$application_name" in examples
    assert "$object_name" in examples
    assert ":CARRIES" in examples
    assert "Show all end-to-end flows that interface with SAP." in examples
    assert "RETURN DISTINCT path" in examples
    assert "CREATE" not in examples


def test_examples_teach_listing_catalogue_node_labels() -> None:
    examples = build_examples_context()

    assert "List all catalogue nodes." in examples
    assert "UNWIND labels(node) AS node_label" in examples
    assert "RETURN DISTINCT node_label" in examples


def test_examples_teach_filtering_and_returning_aggregate_counts() -> None:
    examples = build_examples_context()

    assert "Display all applications with more than three interfaces." in examples
    assert "WITH app, count(DISTINCT interface) AS interface_count" in examples
    assert "WHERE interface_count > $minimum_interface_count" in examples
    assert "app.status AS status, interface_count" in examples
    assert '"minimum_interface_count": 3' in examples


def test_examples_teach_valid_path_hop_counting() -> None:
    examples = build_examples_context()

    assert "Show all integration flows and their hop count." in examples
    assert "size([node IN nodes(path) WHERE node:Integration]) AS hop_count" in examples
    assert "WHERE hop_count > 0" in examples


def test_examples_teach_interface_type_aggregation() -> None:
    examples = build_examples_context()

    assert "For each interface type, show its usage count" in examples
    assert "count(interface) AS usage_count" in examples
    assert "collect(interface.name) AS interface_names" in examples
    assert "GROUP BY" not in examples


def test_examples_teach_information_object_path_filtering() -> None:
    examples = build_examples_context()

    assert "Show end-to-end flows that carry the HR Employee Record." in examples
    assert "integration IN nodes(path)" in examples
    assert '"object_name": "HR Employee Record"' in examples


def test_examples_teach_source_and_target_roles() -> None:
    examples = build_examples_context()

    assert "Which applications are both a source and a target?" in examples
    assert "[:EXPOSES]->(:Interface)-[:SOURCE_OF]" in examples
    assert "[:USES]->(:Interface)<-[:TARGETS]" in examples


def test_examples_teach_unique_direction_and_graph_objects() -> None:
    examples = build_examples_context()

    assert "source.id < target.id" in examples
    assert "collect(DISTINCT carries) AS carries_relationships" in examples
    assert "object LIMIT $limit" in examples
    assert "none(node IN nodes(path)" in examples
    assert '"excluded_name": "Oracle"' in examples
    assert '"empty_name": ""' in examples


def test_examples_teach_typo_resolution_and_multilingual_aggregation() -> None:
    examples = build_examples_context()
    questions = {example["question"] for example in json.loads(examples)}

    assert "show full path between Sforce SRM and SAo S/ANA" in examples
    assert '"source_name": "Salesforce CRM"' in examples
    assert '"target_name": "SAP S/4HANA"' in examples
    assert "Enumera las cinco interfaces utilizadas por más integraciones." in questions
    assert "count(DISTINCT integration) AS integration_count" in examples
