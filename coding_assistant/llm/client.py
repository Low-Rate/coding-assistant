"""Unified LLM client - abstracts over Ollama and LiteLLM backends."""

from dataclasses import dataclass
from typing import Any, AsyncIterator

from coding_assistant.config.settings import get_settings


@dataclass
class StreamChunk:
    """A chunk from streaming response."""

    content: str = ""
    tool_calls: list[dict[str, Any]] | None = None
    done: bool = False
    metadata: dict[str, Any] | None = None


@dataclass
class Message:
    """Unified message format."""

    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class LLMClient:
    """Unified LLM client that delegates to Ollama or LiteLLM."""

    def __init__(self):
        self.settings = get_settings()
        self._ollama_client = None
        self._litellm_client = None

    @property
    def backend(self) -> str:
        return self.settings.llm_backend

    def _get_ollama_client(self):
        """Lazy-load Ollama client."""
        if self._ollama_client is None:
            from coding_assistant.llm.ollama import OllamaClient
            self._ollama_client = OllamaClient()
        return self._ollama_client

    def _get_litellm_client(self):
        """Lazy-load LiteLLM client."""
        if self._litellm_client is None:
            from coding_assistant.llm.litellm import LiteLLMClient
            self._litellm_client = LiteLLMClient()
        return self._litellm_client

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._ollama_client:
            await self._ollama_client.__aexit__(*args)
        if self._litellm_client:
            await self._litellm_client.__aexit__(*args)

    async def chat(
        self,
        messages: list[Message],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
        options: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream chat completions from the configured backend."""
        if self.backend == "litellm":
            async with self._get_litellm_client() as client:
                # Convert to LiteLLM message format
                from coding_assistant.llm.litellm import LiteLLMMessage
                litellm_messages = [
                    LiteLLMMessage(
                        role=m.role,
                        content=m.content,
                        tool_calls=m.tool_calls,
                        tool_call_id=m.tool_call_id,
                        name=m.name,
                    )
                    for m in messages
                ]
                async for chunk in client.chat(
                    messages=litellm_messages,
                    model=model,
                    tools=tools,
                    stream=stream,
                    options=options,
                ):
                    yield chunk
        else:
            async with self._get_ollama_client() as client:
                # Convert to Ollama message format
                from coding_assistant.llm.ollama import OllamaMessage
                ollama_messages = [
                    OllamaMessage(
                        role=m.role,
                        content=m.content or "",
                        tool_calls=m.tool_calls,
                    )
                    for m in messages
                ]
                async for chunk in client.chat(
                    messages=ollama_messages,
                    model=model,
                    tools=tools,
                    stream=stream,
                    options=options,
                ):
                    # Convert Ollama StreamChunk to unified format
                    yield StreamChunk(
                        content=chunk.content,
                        tool_calls=[
                            tc.model_dump() for tc in chunk.tool_calls
                        ] if chunk.tool_calls else None,
                        done=chunk.done,
                        metadata=chunk.metadata,
                    )

    async def chat_once(
        self,
        messages: list[Message],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
    ) -> Any:
        """Non-streaming chat completion."""
        if self.backend == "litellm":
            async with self._get_litellm_client() as client:
                from coding_assistant.llm.litellm import LiteLLMMessage
                litellm_messages = [
                    LiteLLMMessage(
                        role=m.role,
                        content=m.content,
                        tool_calls=m.tool_calls,
                        tool_call_id=m.tool_call_id,
                        name=m.name,
                    )
                    for m in messages
                ]
                return await client.chat_once(
                    messages=litellm_messages,
                    model=model,
                    tools=tools,
                    options=options,
                )
        else:
            async with self._get_ollama_client() as client:
                from coding_assistant.llm.ollama import OllamaMessage
                ollama_messages = [
                    OllamaMessage(
                        role=m.role,
                        content=m.content or "",
                        tool_calls=m.tool_calls,
                    )
                    for m in messages
                ]
                return await client.chat_once(
                    messages=ollama_messages,
                    model=model,
                    tools=tools,
                    options=options,
                )

    async def list_models(self) -> list[str]:
        """List available models."""
        if self.backend == "litellm":
            async with self._get_litellm_client() as client:
                models = await client.list_models()
                return [m.get("id", "") for m in models]
        else:
            async with self._get_ollama_client() as client:
                models = await client.list_models()
                return [m["name"] for m in models]

    async def generate_embeddings(
        self, texts: list[str], model: str | None = None
    ) -> list[list[float]]:
        """Generate embeddings for texts."""
        if self.backend == "litellm":
            async with self._get_litellm_client() as client:
                return await client.generate_embeddings(texts, model)
        else:
            async with self._get_ollama_client() as client:
                return await client.generate_embeddings(texts, model)


def get_llm_client() -> LLMClient:
    """Get the unified LLM client."""
    return LLMClient()