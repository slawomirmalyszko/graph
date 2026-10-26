from __future__ import annotations

import pytest

from integration_catalogue.query.bedrock import (
    AWS_REGION,
    BedrockConfigurationError,
    BedrockResponseError,
    BedrockSettings,
    BedrockTextAdapter,
)


class FakeConverseClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.request: dict | None = None

    def converse(self, **request):
        self.request = request
        return self.response


def test_settings_default_to_stockholm_and_nova_lite(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AWS_REGION",
        "BEDROCK_MODEL_ID",
        "BEDROCK_MAX_TOKENS",
        "BEDROCK_TEMPERATURE",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = BedrockSettings.from_environment()

    assert settings.region == AWS_REGION
    assert settings.model_id == "amazon.nova-lite-v1:0"
    assert settings.max_tokens == 512
    assert settings.temperature == 0


def test_settings_reject_non_stockholm_region(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_REGION", "eu-west-1")

    with pytest.raises(BedrockConfigurationError, match="eu-north-1"):
        BedrockSettings.from_environment()


def test_adapter_sends_bounded_converse_request_and_returns_usage() -> None:
    client = FakeConverseClient(
        {
            "output": {"message": {"content": [{"text": "MATCH (a) RETURN a LIMIT 10"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 120, "outputTokens": 12, "totalTokens": 132},
            "metrics": {"latencyMs": 85},
        }
    )
    settings = BedrockSettings(max_tokens=256, temperature=0)

    generation = BedrockTextAdapter(client, settings).generate(
        system_prompt="Return Cypher.",
        user_prompt="Show applications.",
    )

    assert client.request == {
        "modelId": "amazon.nova-lite-v1:0",
        "messages": [{"role": "user", "content": [{"text": "Show applications."}]}],
        "inferenceConfig": {"maxTokens": 256, "temperature": 0},
        "system": [{"text": "Return Cypher."}],
    }
    assert generation.text == "MATCH (a) RETURN a LIMIT 10"
    assert generation.stop_reason == "end_turn"
    assert generation.total_tokens == 132
    assert generation.latency_ms == 85


def test_adapter_rejects_response_without_text() -> None:
    client = FakeConverseClient({"output": {"message": {"content": []}}})

    with pytest.raises(BedrockResponseError, match="no text"):
        BedrockTextAdapter(client, BedrockSettings()).generate(
            system_prompt="",
            user_prompt="Show applications.",
        )
