from integration_catalogue.query.context import (
    build_examples_context,
    build_schema_context,
    load_catalogue_schema,
)


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
    assert "CREATE" not in examples
