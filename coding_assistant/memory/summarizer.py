"""Conversation summarizer for long-context compression."""

from typing import Any

from coding_assistant.llm.ollama import OllamaClient, OllamaMessage
from coding_assistant.config.settings import get_settings


class Summarizer:
    """Summarizes conversation history to fit token budget."""

    def __init__(self):
        self.settings = get_settings()
        self.client = OllamaClient()

    async def summarize(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
    ) -> str:
        """Summarize a list of messages."""
        max_tokens = max_tokens or self.settings.memory.max_conversation_tokens

        # Build conversation text
        conv_text = "\n\n".join(
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in messages
        )

        if len(conv_text) < max_tokens * 3:  # Rough char-to-token ratio
            return conv_text

        summary_prompt = f"""Summarize the following conversation concisely, preserving:
- Key decisions and outcomes
- Code changes discussed
- Important context for future reference
- User preferences and patterns

Conversation:
{conv_text}

Summary:"""

        async with self.client:
            response = await self.client.chat_once(
                messages=[OllamaMessage(role="user", content=summary_prompt)],
                model=self.settings.memory.summary_model,
                options={"temperature": 0.3},
            )

        return response.message.content

    async def summarize_incremental(
        self,
        previous_summary: str,
        new_messages: list[dict[str, Any]],
    ) -> str:
        """Update summary with new messages."""
        new_text = "\n\n".join(
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in new_messages
        )

        prompt = f"""Update the following summary with new conversation:

Previous Summary:
{previous_summary}

New Messages:
{new_text}

Updated Summary:"""

        async with self.client:
            response = await self.client.chat_once(
                messages=[OllamaMessage(role="user", content=prompt)],
                model=self.settings.memory.summary_model,
                options={"temperature": 0.3},
            )

        return response.message.content


def estimate_tokens(text: str) -> int:
    """Rough token estimation (4 chars ≈ 1 token for English)."""
    return len(text) // 4


def trim_history(
    messages: list[dict[str, Any]],
    max_tokens: int,
    keep_recent: int = 10,
) -> list[dict[str, Any]]:
    """Trim history to fit token budget, keeping recent messages."""
    if not messages:
        return []

    # Always keep recent messages
    recent = messages[-keep_recent:]
    older = messages[:-keep_recent]

    # Estimate tokens for recent
    recent_tokens = sum(estimate_tokens(m.get("content", "")) for m in recent)

    if recent_tokens >= max_tokens:
        return recent  # Even recent exceeds budget

    # Add older messages until budget
    remaining = max_tokens - recent_tokens
    kept_older = []

    for msg in reversed(older):
        tokens = estimate_tokens(msg.get("content", ""))
        if tokens <= remaining:
            kept_older.insert(0, msg)
            remaining -= tokens
        else:
            break

    return kept_older + recent