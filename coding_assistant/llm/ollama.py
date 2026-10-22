"""Ollama client with streaming chat completions."""

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx
from pydantic import BaseModel

from coding_assistant.config.settings import get_settings


class OllamaMessage(BaseModel):
    """Ollama chat message."""

    role: str
    content: str = ""
    images: list[str] | None = None
    tool_calls: list[dict[str, Any]] | None = None


class OllamaToolCall(BaseModel):
    """Ollama tool call."""

    function: dict[str, Any]


class OllamaResponse(BaseModel):
    """Ollama chat response."""

    model: str
    created_at: str
    message: OllamaMessage
    done: bool
    total_duration: int | None = None
    load_duration: int | None = None
    prompt_eval_count: int | None = None
    prompt_eval_duration: int | None = None
    eval_count: int | None = None
    eval_duration: int | None = None


@dataclass
class StreamChunk:
    """A chunk from streaming response."""

    content: str = ""
    tool_calls: list[OllamaToolCall] | None = None
    done: bool = False
    metadata: dict[str, Any] | None = None


class OllamaClient:
    """Async Ollama client with streaming support."""

    def __init__(self, host: str | None = None, timeout: float | None = None):
        self.settings = get_settings()
        self.host = host or self.settings.ollama.host
        self.timeout = timeout or self.settings.ollama.timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OllamaClient":
        self._client = httpx.AsyncClient(
            base_url=self.host,
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("OllamaClient not initialized. Use async context manager.")
        return self._client

    async def chat(
        self,
        messages: list[OllamaMessage],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
        options: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream chat completions from Ollama."""
        payload = {
            "model": model or self.settings.ollama.default_model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "stream": stream,
            "options": options or {},
        }
        if tools:
            payload["tools"] = tools

        async with self.client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    resp = OllamaResponse(**data)
                    yield StreamChunk(
                        content=resp.message.content,
                        tool_calls=[
                            OllamaToolCall(**tc) for tc in (resp.message.tool_calls or [])
                        ]
                        if resp.message.tool_calls
                        else None,
                        done=resp.done,
                        metadata={
                            "total_duration": resp.total_duration,
                            "eval_count": resp.eval_count,
                            "eval_duration": resp.eval_duration,
                        }
                        if resp.done
                        else None,
                    )
                except json.JSONDecodeError:
                    continue

    async def chat_once(
        self,
        messages: list[OllamaMessage],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
    ) -> OllamaResponse:
        """Non-streaming chat completion."""
        payload = {
            "model": model or self.settings.ollama.default_model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "stream": False,
            "options": options or {},
        }
        if tools:
            payload["tools"] = tools

        response = await self.client.post("/api/chat", json=payload)
        response.raise_for_status()
        return OllamaResponse(**response.json())

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models."""
        response = await self.client.get("/api/tags")
        response.raise_for_status()
        return response.json().get("models", [])

    async def pull_model(self, name: str, stream: bool = True) -> AsyncIterator[dict[str, Any]]:
        """Pull a model from Ollama registry."""
        async with self.client.stream(
            "POST", "/api/pull", json={"name": name, "stream": stream}
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    yield json.loads(line)

    async def show_model(self, name: str) -> dict[str, Any]:
        """Show model details."""
        response = await self.client.post("/api/show", json={"name": name})
        response.raise_for_status()
        return response.json()

    async def delete_model(self, name: str) -> None:
        """Delete a model."""
        response = await self.client.delete("/api/delete", json={"name": name})
        response.raise_for_status()

    async def generate_embeddings(
        self, texts: list[str], model: str | None = None
    ) -> list[list[float]]:
        """Generate embeddings for texts."""
        payload = {
            "model": model or "nomic-embed-text",
            "prompt": texts,
        }
        response = await self.client.post("/api/embed", json=payload)
        response.raise_for_status()
        return response.json().get("embeddings", [])


async def get_available_models() -> list[str]:
    """Get list of available model names."""
    async with OllamaClient() as client:
        models = await client.list_models()
        return [m["name"] for m in models]


async def ensure_model_available(model: str) -> bool:
    """Check if model is available, pull if not."""
    async with OllamaClient() as client:
        models = await client.list_models()
        available = [m["name"] for m in models]
        if model in available:
            return True
        # Try to pull
        async for _ in client.pull_model(model):
            pass
        return True