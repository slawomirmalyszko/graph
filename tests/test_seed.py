from copy import deepcopy

import pytest

from integration_catalogue.seed import (
    DEFAULT_SEED_PATH,
    SeedValidationError,
    iter_cypher_statements,
    read_seed,
    validate_seed,
)


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

