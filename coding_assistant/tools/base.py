"""Base tool system with decorator-based registration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints, Union, Optional
import inspect


@dataclass
class ToolResult:
    """Result of tool execution."""

    success: bool
    output: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolSpec:
    """Tool specification for LLM function calling."""

    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str] = field(default_factory=list)
    confirm: bool = False  # Whether to ask for confirmation before execution


class Tool(ABC):
    """Base class for tools."""

    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str] = field(default_factory=list)
    confirm: bool = False

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool."""
        pass

    def to_spec(self) -> ToolSpec:
        """Convert to tool specification."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            required=self.required,
            confirm=self.confirm,
        )


class ToolRegistry:
    """Registry for managing tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._functions: dict[str, Callable] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def register_function(
        self,
        func: Callable,
        name: str | None = None,
        description: str | None = None,
        confirm: bool = False,
    ) -> None:
        """Register a function as a tool."""
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            param_type = type_hints.get(param_name, str)
            properties[param_name] = self._type_to_schema(param_type)
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        tool_spec = ToolSpec(
            name=name or func.__name__,
            description=description or func.__doc__ or "",
            parameters={"type": "object", "properties": properties, "required": required},
            required=required,
            confirm=confirm,
        )

        # Create a tool wrapper
        class FunctionTool(Tool):
            def __init__(self, func: Callable, spec: ToolSpec):
                self._func = func
                self.name = spec.name
                self.description = spec.description
                self.parameters = spec.parameters
                self.required = spec.required
                self.confirm = spec.confirm

            async def execute(self, **kwargs: Any) -> ToolResult:
                try:
                    if inspect.iscoroutinefunction(self._func):
                        result = await self._func(**kwargs)
                    else:
                        result = self._func(**kwargs)

                    # If the function already returns a ToolResult, use it directly
                    if isinstance(result, ToolResult):
                        return result
                    return ToolResult(success=True, output=str(result))
                except Exception as e:
                    return ToolResult(success=False, error=str(e))

        self._tools[tool_spec.name] = FunctionTool(func, tool_spec)
        self._functions[tool_spec.name] = func

    def _type_to_schema(self, typ: Any) -> dict[str, Any]:
        """Convert Python type to JSON schema."""
        from typing import get_origin, get_args

        origin = get_origin(typ)
        args = get_args(typ)

        if origin is None:
            # Simple type
            type_map = {
                str: "string",
                int: "integer",
                float: "number",
                bool: "boolean",
                list: "array",
                dict: "object",
            }
            return {"type": type_map.get(typ, "string")}

        if origin in (list, tuple):
            item_schema = self._type_to_schema(args[0]) if args else {"type": "string"}
            return {"type": "array", "items": item_schema}

        if origin is dict:
            return {"type": "object"}

        if origin in (Union, Optional):
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return self._type_to_schema(non_none[0])

        return {"type": "string"}

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def specs(self) -> list[ToolSpec]:
        """Get all tool specifications for LLM."""
        return [t.to_spec() for t in self._tools.values()]


# Global registry
registry = ToolRegistry()


def tool(
    name: str | None = None,
    description: str | None = None,
    confirm: bool = False,
) -> Callable:
    """Decorator to register a function as a tool."""

    def decorator(func: Callable) -> Callable:
        registry.register_function(func, name, description, confirm)
        return func

    return decorator