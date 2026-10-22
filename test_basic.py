"""Basic functionality test without Ollama."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from coding_assistant.agent.loop import AgentLoop
from coding_assistant.agent.prompt_builder import PromptContext
from coding_assistant.agent.session import SessionManager
from coding_assistant.tools import registry
from coding_assistant.config.settings import settings


async def test_tool_execution():
    """Test tool execution directly."""
    print("Testing tool execution...")

    # Test read_file
    result = await registry.get("read_file").execute(
        path="D:/gunmu/啊鹏可捞/coding-assistant/README.md",
        limit=10
    )
    assert result.success
    print(f"[OK] read_file works: {result.output[:50]}...")

    # Test list_dir
    result = await registry.get("list_dir").execute(
        path="D:/gunmu/啊鹏可捞/coding-assistant",
        depth=2
    )
    assert result.success
    print(f"[OK] list_dir works: {len(result.output.splitlines())} lines")

    # Test grep
    result = await registry.get("grep").execute(
        pattern="class",
        path="D:/gunmu/啊鹏可捞/coding-assistant/coding_assistant",
        max_results=5
    )
    assert result.success
    print(f"[OK] grep works: {result.metadata.get('matches', 0)} matches")

    print("\nAll tool tests passed!")


async def test_session_manager():
    """Test session persistence."""
    print("\nTesting session manager...")

    manager = SessionManager()
    session = manager.create_session("D:/gunmu/啊鹏可捞/coding-assistant")
    print(f"[OK] Created session: {session.id}")

    from coding_assistant.agent.session import Message
    msg = Message(role="user", content="Hello")
    manager.add_message(msg, session)
    print(f"[OK] Added message")

    manager.save_session(session)
    print(f"[OK] Saved session")

    loaded = manager.load_session(session.id)
    assert loaded is not None
    assert len(loaded.messages) == 1
    print(f"[OK] Loaded session: {len(loaded.messages)} messages")

    print("\nSession manager tests passed!")


async def test_prompt_builder():
    """Test prompt building."""
    print("\nTesting prompt builder...")

    from coding_assistant.agent.prompt_builder import PromptContext, build_system_prompt

    context = PromptContext(
        project_root="D:/gunmu/啊鹏可捞/coding-assistant",
        working_dir="D:/gunmu/啊鹏可捞/coding-assistant",
        active_files=["README.md"],
    )

    prompt = build_system_prompt(context)
    assert "coding assistant" in prompt.lower()
    assert "tools" in prompt.lower()
    print(f"[OK] System prompt built: {len(prompt)} chars")

    print("\nPrompt builder tests passed!")


async def main():
    """Run all tests."""
    await test_tool_execution()
    await test_session_manager()
    await test_prompt_builder()
    print("\n[OK] All basic tests passed!")


if __name__ == "__main__":
    asyncio.run(main())