"""Tools package - imports all tools to register them."""

from coding_assistant.tools import base, bash, file_ops, git_tool

# Re-export key symbols
from coding_assistant.tools.base import Tool, ToolRegistry, ToolResult, ToolSpec, registry, tool

__all__ = [
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "registry",
    "tool",
]