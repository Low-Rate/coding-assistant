"""Tool executor for running LLM tool calls."""

from dataclasses import dataclass
from typing import Any

from coding_assistant.tools.base import ToolResult, registry


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""

    name: str
    arguments: dict[str, Any]
    id: str | None = None


@dataclass
class ToolExecutionResult:
    """Result of tool execution."""

    tool_call: ToolCall
    result: ToolResult
    confirmed: bool = False


class ToolExecutor:
    """Executes tool calls from the LLM."""

    def __init__(self, confirm_callback=None):
        self.confirm_callback = confirm_callback

    async def execute(self, tool_call: ToolCall, auto_confirm: bool = False) -> ToolExecutionResult:
        """Execute a single tool call."""
        tool = registry.get(tool_call.name)
        if not tool:
            return ToolExecutionResult(
                tool_call=tool_call,
                result=ToolResult(success=False, error=f"Unknown tool: {tool_call.name}"),
            )

        # Check if confirmation needed
        needs_confirm = tool.confirm and not auto_confirm
        confirmed = False

        if needs_confirm and self.confirm_callback:
            confirmed = await self.confirm_callback(tool_call)
            if not confirmed:
                return ToolExecutionResult(
                    tool_call=tool_call,
                    result=ToolResult(success=False, error="User cancelled"),
                    confirmed=False,
                )

        # Execute tool
        try:
            result = await tool.execute(**tool_call.arguments)
        except Exception as e:
            result = ToolResult(success=False, error=f"Execution error: {e}")

        return ToolExecutionResult(
            tool_call=tool_call,
            result=result,
            confirmed=confirmed or not needs_confirm,
        )

    async def execute_batch(
        self, tool_calls: list[ToolCall], auto_confirm: bool = False
    ) -> list[ToolExecutionResult]:
        """Execute multiple tool calls sequentially."""
        results = []
        for tc in tool_calls:
            result = await self.execute(tc, auto_confirm)
            results.append(result)
            # Stop on first failure if not auto_confirm
            if not result.result.success and not auto_confirm:
                break
        return results


def parse_tool_calls(llm_tool_calls: list[dict[str, Any]]) -> list[ToolCall]:
    """Parse tool calls from LLM response format."""
    calls = []
    for tc in llm_tool_calls:
        if isinstance(tc, dict):
            # Ollama format: {"function": {"name": "...", "arguments": {...}}}
            if "function" in tc:
                func = tc["function"]
                calls.append(
                    ToolCall(
                        name=func.get("name", ""),
                        arguments=func.get("arguments", {}),
                        id=tc.get("id"),
                    )
                )
            # Direct format: {"name": "...", "arguments": {...}}
            elif "name" in tc:
                calls.append(
                    ToolCall(
                        name=tc["name"],
                        arguments=tc.get("arguments", {}),
                        id=tc.get("id"),
                    )
                )
    return calls