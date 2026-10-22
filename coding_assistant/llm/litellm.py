"""LiteLLM client (OpenAI-compatible) with streaming chat completions.

Supports LiteLLM proxy v1.106+ which implements OpenAI-compatible API.
"""

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx
from pydantic import BaseModel

from coding_assistant.config.settings import get_settings


class LiteLLMMessage(BaseModel):
    """LiteLLM/OpenAI chat message."""

    role: str | None = None
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class LiteLLMToolCall(BaseModel):
    """LiteLLM tool call."""

    id: str
    type: str = "function"
    function: dict[str, Any]


class LiteLLMChoice(BaseModel):
    """LiteLLM choice (supports both streaming and non-streaming)."""

    index: int
    delta: LiteLLMMessage | None = None  # For streaming
    message: LiteLLMMessage | None = None  # For non-streaming
    finish_reason: str | None = None


class LiteLLMStreamResponse(BaseModel):
    """LiteLLM streaming response."""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[LiteLLMChoice]
    usage: dict[str, Any] | None = None


class LiteLLMResponse(BaseModel):
    """LiteLLM non-streaming response."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[LiteLLMChoice]
    usage: dict[str, Any] | None = None


@dataclass
class StreamChunk:
    """A chunk from streaming response."""

    content: str = ""
    tool_calls: list[LiteLLMToolCall] | None = None
    done: bool = False
    metadata: dict[str, Any] | None = None


class LiteLLMClient:
    """Async LiteLLM client with streaming support (OpenAI-compatible API)."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        extra_headers: dict[str, str] | None = None,
    ):
        self.settings = get_settings()
        self.base_url = base_url or self.settings.litellm.base_url
        self.api_key = api_key or self.settings.litellm.api_key
        self.timeout = timeout or self.settings.litellm.timeout
        self.extra_headers = extra_headers or self.settings.litellm.extra_headers
        self._client: httpx.AsyncClient | None = None

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update(self.extra_headers)
        return headers

    async def __aenter__(self) -> "LiteLLMClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers=self._get_headers(),
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("LiteLLMClient not initialized. Use async context manager.")
        return self._client

    def _convert_messages(self, messages: list[LiteLLMMessage]) -> list[dict[str, Any]]:
        """Convert messages to OpenAI format."""
        result = []
        for m in messages:
            msg = {"role": m.role}
            if m.content is not None:
                msg["content"] = m.content
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            if m.name:
                msg["name"] = m.name
            result.append(msg)
        return result

    def _convert_tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        """Convert tools to OpenAI format (already compatible)."""
        return tools

    async def chat(
        self,
        messages: list[LiteLLMMessage],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
        options: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream chat completions from LiteLLM."""
        payload = {
            "model": model or self.settings.litellm.default_model,
            "messages": self._convert_messages(messages),
            "stream": stream,
        }
        if tools:
            payload["tools"] = self._convert_tools(tools)
        if options:
            # Map Ollama options to OpenAI params
            if "temperature" in options:
                payload["temperature"] = options["temperature"]
            if "top_p" in options:
                payload["top_p"] = options["top_p"]
            if "num_predict" in options:
                payload["max_tokens"] = options["num_predict"]

        async with self.client.stream("POST", "/v1/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        resp = LiteLLMStreamResponse(**data)
                        choice = resp.choices[0] if resp.choices else None
                        if choice and choice.delta:
                            content = choice.delta.content or ""
                            tool_calls = choice.delta.tool_calls
                            yield StreamChunk(
                                content=content,
                                tool_calls=[
                                    LiteLLMToolCall(**tc) for tc in tool_calls
                                ] if tool_calls else None,
                                done=choice.finish_reason is not None,
                                metadata={
                                    "usage": resp.usage,
                                    "model": resp.model,
                                } if choice.finish_reason else None,
                            )
                    except json.JSONDecodeError:
                        continue

    async def chat_once(
        self,
        messages: list[LiteLLMMessage],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
    ) -> LiteLLMResponse:
        """Non-streaming chat completion."""
        payload = {
            "model": model or self.settings.litellm.default_model,
            "messages": self._convert_messages(messages),
            "stream": False,
        }
        if tools:
            payload["tools"] = self._convert_tools(tools)
        if options:
            if "temperature" in options:
                payload["temperature"] = options["temperature"]
            if "top_p" in options:
                payload["top_p"] = options["top_p"]
            if "num_predict" in options:
                payload["max_tokens"] = options["num_predict"]

        response = await self.client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        # Handle both streaming-style (delta) and non-streaming (message) response formats
        if data.get("choices") and "message" in data["choices"][0] and "delta" not in data["choices"][0]:
            # Convert message format to delta format for consistency
            for choice in data["choices"]:
                choice["delta"] = choice.get("message", {})

        return LiteLLMResponse(**data)

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models from LiteLLM."""
        response = await self.client.get("/v1/models")
        response.raise_for_status()
        return response.json().get("data", [])

    async def generate_embeddings(
        self, texts: list[str], model: str | None = None
    ) -> list[list[float]]:
        """Generate embeddings for texts (OpenAI-compatible)."""
        payload = {
            "model": model or self.settings.litellm.embedding_model,
            "input": texts,
        }
        response = await self.client.post("/v1/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data.get("data", [])]


async def get_available_models() -> list[str]:
    """Get list of available model names."""
    async with LiteLLMClient() as client:
        models = await client.list_models()
        return [m.get("id", "") for m in models]


async def ensure_model_available(model: str) -> bool:
    """Check if model is available via LiteLLM."""
    async with LiteLLMClient() as client:
        models = await client.list_models()
        available = [m.get("id", "") for m in models]
        return model in available