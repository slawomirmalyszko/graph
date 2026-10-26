"""Amazon Bedrock Converse API adapter for text generation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

AWS_REGION = "eu-north-1"
DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"


class BedrockConfigurationError(ValueError):
    """Raised when Bedrock settings violate the project configuration."""


class BedrockResponseError(RuntimeError):
    """Raised when Bedrock returns no usable generated text."""


@dataclass(frozen=True)
class BedrockSettings:
    region: str = AWS_REGION
    model_id: str = DEFAULT_MODEL_ID
    max_tokens: int = 512
    temperature: float = 0.0

    @classmethod
    def from_environment(cls) -> BedrockSettings:
        region = os.getenv("AWS_REGION", AWS_REGION).strip()
        model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID).strip()

        try:
            max_tokens = int(os.getenv("BEDROCK_MAX_TOKENS", "512"))
            temperature = float(os.getenv("BEDROCK_TEMPERATURE", "0"))
        except ValueError as error:
            raise BedrockConfigurationError(
                "BEDROCK_MAX_TOKENS and BEDROCK_TEMPERATURE must be numeric."
            ) from error

        if region != AWS_REGION:
            raise BedrockConfigurationError(
                f"AWS_REGION must remain {AWS_REGION} for the Integration Catalogue project."
            )
        if not model_id:
            raise BedrockConfigurationError("BEDROCK_MODEL_ID cannot be empty.")
        if not 1 <= max_tokens <= 4096:
            raise BedrockConfigurationError("BEDROCK_MAX_TOKENS must be between 1 and 4096.")
        if not 0 <= temperature <= 1:
            raise BedrockConfigurationError("BEDROCK_TEMPERATURE must be between 0 and 1.")

        return cls(
            region=region,
            model_id=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
        )


@dataclass(frozen=True)
class BedrockGeneration:
    text: str
    stop_reason: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int | None


class ConverseClient(Protocol):
    def converse(self, **request: Any) -> dict[str, Any]:
        """Send one Converse API request."""
        ...


def create_bedrock_runtime_client(settings: BedrockSettings) -> ConverseClient:
    """Create a regional Bedrock Runtime client using the default credential chain."""
    import boto3
    from botocore.config import Config

    session = boto3.Session(region_name=settings.region)
    return session.client(
        "bedrock-runtime",
        config=Config(
            retries={"total_max_attempts": 5, "mode": "adaptive"},
            connect_timeout=5,
            read_timeout=60,
        ),
    )


class BedrockTextAdapter:
    """Small synchronous adapter around the Bedrock Converse API."""

    def __init__(self, client: ConverseClient, settings: BedrockSettings) -> None:
        self._client = client
        self._settings = settings

    def generate(self, *, system_prompt: str, user_prompt: str) -> BedrockGeneration:
        request: dict[str, Any] = {
            "modelId": self._settings.model_id,
            "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
            "inferenceConfig": {
                "maxTokens": self._settings.max_tokens,
                "temperature": self._settings.temperature,
            },
        }
        if system_prompt:
            request["system"] = [{"text": system_prompt}]

        response = self._client.converse(**request)
        content = response.get("output", {}).get("message", {}).get("content", [])
        text = "".join(block.get("text", "") for block in content if "text" in block).strip()
        if not text:
            raise BedrockResponseError("Bedrock returned no text content.")

        usage = response.get("usage", {})
        metrics = response.get("metrics", {})
        return BedrockGeneration(
            text=text,
            stop_reason=response.get("stopReason", "unknown"),
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            total_tokens=usage.get("totalTokens", 0),
            latency_ms=metrics.get("latencyMs"),
        )
