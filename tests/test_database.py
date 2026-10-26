from __future__ import annotations

import pytest

from integration_catalogue.database import (
    AuraConfigurationError,
    AuraSettings,
    verify_and_summarize,
)


def test_settings_require_all_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(AuraConfigurationError, match="NEO4J_PASSWORD"):
        AuraSettings.from_environment()


def test_settings_reject_non_aura_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")

    with pytest.raises(AuraConfigurationError, match=r"neo4j\+s"):
        AuraSettings.from_environment()


class FakeResult:
    def __init__(self, records: list[dict[str, int | str]]) -> None:
        self.records = records

    def __iter__(self):
        return iter(self.records)

    def single(self, *, strict: bool) -> dict[str, int | str]:
        assert strict
        assert len(self.records) == 1
        return self.records[0]


class FakeTransaction:
    def run(self, query: str, **parameters: object) -> FakeResult:
        if "relationship" in query:
            return FakeResult([{"count": 76}])
        assert parameters["labels"] == [
            "Application",
            "Interface",
            "Integration",
            "InformationObject",
        ]
        return FakeResult(
            [
                {"label": "Application", "count": 16},
                {"label": "Interface", "count": 23},
                {"label": "Integration", "count": 20},
                {"label": "InformationObject", "count": 12},
            ]
        )


class FakeSession:
    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute_read(self, callback):
        return callback(FakeTransaction())


class FakeDriver:
    def __init__(self) -> None:
        self.verified = False
        self.session_options: dict[str, object] = {}

    def verify_connectivity(self) -> None:
        self.verified = True

    def session(self, **options: object) -> FakeSession:
        self.session_options = options
        return FakeSession()


def test_summary_uses_verified_read_session() -> None:
    driver = FakeDriver()

    summary = verify_and_summarize(driver, "neo4j")

    assert driver.verified
    assert driver.session_options["database"] == "neo4j"
    assert "default_access_mode" in driver.session_options
    assert summary.nodes == 71
    assert summary.relationships == 76
