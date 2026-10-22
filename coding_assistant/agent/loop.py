"""Main agent loop - ReAct pattern implementation."""

from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from coding_assistant.llm.client import LLMClient, Message, StreamChunk
from coding_assistant.agent.prompt_builder import PromptContext, build_messages, format_tool_result
from coding_assistant.agent.tool_executor import ToolExecutor, ToolCall, parse_tool_calls
from coding_assistant.memory import Retriever, VectorStore
from coding_assistant.config.settings import get_settings
from coding_assistant.tools.base import registry


@dataclass
class AgentState:
    """Current state of the agent."""

    context: PromptContext
    messages: list[dict[str, Any]] = field(default_factory=list)
    turn_count: int = 0
    max_turns: int = 10


class AgentLoop:
    """Main ReAct loop for the coding assistant."""

    def __init__(self, context: PromptContext, confirm_callback=None):
        self.settings = get_settings()
        self.state = AgentState(context=context)
        self.executor = ToolExecutor(confirm_callback)
        self.client = LLMClient()

        # Initialize memory system
        self.vector_store = VectorStore()
        self.retriever = Retriever(self.vector_store)

        # Retrieve relevant context for the user message
        self._enhance_context_with_memory()

    def _enhance_context_with_memory(self):
        """Retrieve and add relevant memory to context."""
        # Get project context
        project_context = self.retriever.get_project_context(self.state.context.project_root)
        self.state.context.project_context = project_context

        # Get recent conversation summary if needed
        from coding_assistant.memory.summarizer import estimate_tokens
        total_tokens = sum(estimate_tokens(m.get("content", "")) for m in self.state.context.conversation_history)
        if total_tokens > self.settings.memory.summary_threshold:
            # Would summarize here
            pass

    def _retrieve_relevant_code(self, query: str) -> list[dict[str, Any]]:
        """Retrieve code chunks relevant to the query."""
        return self.retriever.retrieve_code(query, n_results=5)

    async def run(self, user_message: str) -> AsyncIterator[dict[str, Any]]:
        """Run the agent loop, yielding events."""
        # Retrieve relevant code context for this query
        memory_results = self.retriever.retrieve_code(user_message, n_results=5)
        if memory_results:
            memory_context = "\n\n".join(
                f"--- {r['metadata'].get('file_path', 'unknown')} ({r['metadata'].get('chunk_name', '')}) ---\n{r['content']}"
                for r in memory_results
            )
            self.state.context.memory_context = memory_context

        # Add user message to context
        self.state.context.conversation_history.append(
            {"role": "user", "content": user_message}
        )

        # Build initial messages
        self.state.messages = build_messages(self.state.context, user_message)

        # Get model for current backend
        model = self._get_default_model()

        async with self.client:
            while self.state.turn_count < self.state.max_turns:
                self.state.turn_count += 1

                # Stream response from LLM
                full_content = ""
                tool_calls_buffer: list[dict[str, Any]] = []

                yield {"type": "turn_start", "turn": self.state.turn_count}

                async for chunk in self.client.chat(
                    messages=[Message(**m) for m in self.state.messages],
                    model=model,
                    tools=registry.specs_to_openai() if hasattr(registry, "specs_to_openai") else None,
                    stream=True,
                ):
                    if chunk.content:
                        full_content += chunk.content
                        yield {"type": "content", "content": chunk.content}

                    if chunk.tool_calls:
                        tool_calls_buffer.extend(chunk.tool_calls)

                    if chunk.done and chunk.metadata:
                        yield {"type": "usage", "metadata": chunk.metadata}

                # Add assistant message to history
                assistant_msg = {"role": "assistant", "content": full_content}
                if tool_calls_buffer:
                    assistant_msg["tool_calls"] = tool_calls_buffer
                self.state.messages.append(assistant_msg)
                self.state.context.conversation_history.append(assistant_msg)

                # If no tool calls, we're done
                if not tool_calls_buffer:
                    yield {"type": "turn_end", "turn": self.state.turn_count}
                    break

                # Execute tool calls
                parsed_calls = parse_tool_calls(tool_calls_buffer)
                yield {"type": "tool_calls", "calls": [tc.name for tc in parsed_calls]}

                exec_results = await self.executor.execute_batch(parsed_calls)

                for exec_result in exec_results:
                    yield {"type": "tool_result", "result": exec_result}

                    # Add tool result to messages
                    tool_msg = {
                        "role": "tool",
                        "content": format_tool_result(exec_result.result, exec_result.tool_call.name),
                        "tool_call_id": exec_result.tool_call.id,
                    }
                    self.state.messages.append(tool_msg)
                    self.state.context.conversation_history.append(tool_msg)

                    # Track recent tool calls for context
                    self.state.context.recent_tool_calls.append(
                        {
                            "tool": exec_result.tool_call.name,
                            "args": exec_result.tool_call.arguments,
                            "success": exec_result.result.success,
                        }
                    )

                yield {"type": "turn_end", "turn": self.state.turn_count}

            else:
                yield {"type": "max_turns_reached"}

        yield {"type": "done"}

    def _get_default_model(self) -> str:
        """Get default model for current backend."""
        if self.settings.llm_backend == "litellm":
            return self.settings.litellm.default_model
        else:
            return self.settings.ollama.default_model


# Add helper to registry for OpenAI/LiteLLM format
def specs_to_openai() -> list[dict[str, Any]]:
    """Convert tool specs to OpenAI function calling format."""
    openai_tools = []
    for spec in registry.specs():
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
        )
    return openai_tools


# Monkey-patch for now
import coding_assistant.tools.base as base_module
base_module.registry.specs_to_openai = specs_to_openai

# Also keep Ollama format for backwards compatibility
def specs_to_ollama() -> list[dict[str, Any]]:
    """Convert tool specs to Ollama function calling format."""
    return specs_to_openai()  # Same format

base_module.registry.specs_to_ollama = specs_to_ollama