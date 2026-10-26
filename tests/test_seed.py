from copy import deepcopy

import pytest

from integration_catalogue.seed import (
    DEFAULT_CONSTRAINTS_PATH,
    DEFAULT_SEED_PATH,
    INVALID_PLATFORMS_QUERY,
    SeedValidationError,
    iter_cypher_statements,
    load_seed,
    read_seed,
    validate_seed,
)


class _Counters:
    def __init__(
        self,
        *,
        constraints_added: int = 0,
        indexes_added: int = 0,
        nodes_created: int = 0,
        relationships_created: int = 0,
    ) -> None:
        self.constraints_added = constraints_added
        self.indexes_added = indexes_added
        self.nodes_created = nodes_created
        self.relationships_created = relationships_created


class _Result:
    def __init__(self, counters: _Counters) -> None:
        self.counters = counters

    def consume(self) -> "_Result":
        return self


class _Session:
    def __enter__(self) -> "_Session":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def run(self, query: str, **parameters: object) -> _Result:
        rows = parameters.get("rows", [])
        if query.startswith("CREATE CONSTRAINT"):
            return _Result(_Counters(constraints_added=1))
        if query.startswith("CREATE INDEX"):
            return _Result(_Counters(indexes_added=1))
        if "MERGE (node:" in query:
            return _Result(_Counters(nodes_created=len(rows)))
        return _Result(_Counters(relationships_created=len(rows)))


class _Driver:
    def session(self) -> _Session:
        return _Session()


def test_repository_seed_is_valid() -> None:
    validate_seed(read_seed(DEFAULT_SEED_PATH))


def test_each_integration_has_exactly_one_source_and_target() -> None:
    seed = read_seed(DEFAULT_SEED_PATH)
    seed["relationships"]["TARGETS"].pop()

    with pytest.raises(SeedValidationError, match="exactly one source and target"):
        validate_seed(seed)


def test_platform_apm_id_must_reference_platform_application() -> None:
    seed = read_seed(DEFAULT_SEED_PATH)
    invalid_seed = deepcopy(seed)
    invalid_seed["nodes"]["Integration"][0]["platform_apm_id"] = "APM-1001"

    with pytest.raises(SeedValidationError, match="missing or non-platform"):
        validate_seed(invalid_seed)


def test_relationship_endpoint_labels_are_checked() -> None:
    seed = read_seed(DEFAULT_SEED_PATH)
    seed["relationships"]["SOURCE_OF"][0]["from"] = "app:salesforce-crm"

    with pytest.raises(SeedValidationError, match="must reference a Interface"):
        validate_seed(seed)


def test_constraint_file_contains_individual_statements() -> None:
    statements = list(iter_cypher_statements("// comment\nCREATE ONE;\nCREATE TWO;"))

    assert statements == ["CREATE ONE", "CREATE TWO"]


def test_platform_verification_filters_after_optional_match() -> None:
    optional_match = INVALID_PLATFORMS_QUERY.index("OPTIONAL MATCH")
    new_scope = INVALID_PLATFORMS_QUERY.index("WITH integration, platform")
    filter_clause = INVALID_PLATFORMS_QUERY.index("WHERE platform IS NULL")

    assert optional_match < new_scope < filter_clause


def test_loader_reports_progress_without_connection_details(
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed = read_seed(DEFAULT_SEED_PATH)

    load_seed(_Driver(), seed, DEFAULT_CONSTRAINTS_PATH)

    output = capsys.readouterr().out
    assert "Seed validated: 71 nodes and 76 relationships" in output
    assert "Application nodes processed: 16 (created: 16, matched/updated: 0)" in output
    assert "Integration nodes processed: 20 (created: 20, matched/updated: 0)" in output
    assert "CARRIES relationships processed: 20 (created: 20, matched/updated: 0)" in output
    assert "neo4j+s://" not in output

