"""Prompt builder for assembling context and system prompts."""

from dataclasses import dataclass, field
from typing import Any

from coding_assistant.tools.base import registry


@dataclass
class PromptContext:
    """Context for prompt building."""

    project_root: str
    working_dir: str
    active_files: list[str] = field(default_factory=list)
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    project_context: str = ""
    memory_context: str = ""
    recent_tool_calls: list[dict[str, Any]] = field(default_factory=list)


SYSTEM_PROMPT = """You are a coding assistant running locally via Ollama. You help users write, edit, and understand code.

## Capabilities
- Read, write, and edit files in the project
- Execute bash commands (with confirmation for destructive operations)
- Search code with grep/glob
- Git operations (status, diff, commit, log)
- Access project context and memory

## Guidelines
1. **Be concise** - Prefer code over explanation when showing solutions
2. **Use tools** - Don't guess file contents; use read_file, grep, etc.
3. **Confirm destructive actions** - The system will ask for confirmation before write/edit/bash
4. **Follow project conventions** - Check existing code style, patterns, and structure
5. **Explain complex changes** - For multi-file edits, summarize what you're doing

## Tool Usage
- Always use the exact tool names and parameters as specified
- For file paths, use relative paths from the project root
- Combine related operations when possible

## Memory & Context
- You have access to project-level context (structure, conventions)
- Conversation history is maintained across sessions
- Relevant code snippets are retrieved via RAG when needed

Current project: {project_root}
Working directory: {working_dir}
"""


def build_system_prompt(context: PromptContext) -> str:
    """Build the system prompt with context."""
    prompt = SYSTEM_PROMPT.format(
        project_root=context.project_root,
        working_dir=context.working_dir,
    )

    if context.project_context:
        prompt += f"\n## Project Context\n{context.project_context}\n"

    if context.memory_context:
        prompt += f"\n## Relevant Memory\n{context.memory_context}\n"

    if context.active_files:
        prompt += f"\n## Active Files\n" + "\n".join(f"- {f}" for f in context.active_files) + "\n"

    # Add tool specifications
    tools = registry.specs()
    if tools:
        prompt += "\n## Available Tools\n"
        for tool in tools:
            params = tool.parameters.get("properties", {})
            param_desc = ", ".join(
                f"{name}: {info.get('type', 'string')}" for name, info in params.items()
            )
            prompt += f"- **{tool.name}**({param_desc}): {tool.description}\n"

    return prompt


def build_messages(context: PromptContext, user_message: str) -> list[dict[str, Any]]:
    """Build message list for LLM."""
    messages = [
        {"role": "system", "content": build_system_prompt(context)},
    ]

    # Add conversation history (trimmed)
    max_history = 20
    for msg in context.conversation_history[-max_history:]:
        messages.append(msg)

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    return messages


def format_tool_result(result: Any, tool_name: str) -> str:
    """Format tool result for LLM consumption."""
    if hasattr(result, "success"):
        if result.success:
            return f"[Tool: {tool_name}] Success\n{result.output}"
        else:
            return f"[Tool: {tool_name}] Error: {result.error}"
    return f"[Tool: {tool_name}] {result}"