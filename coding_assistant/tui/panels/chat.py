"""Chat panel for displaying conversation."""

from textual.widgets import RichLog
from textual.containers import VerticalScroll
from textual.message import Message
from typing import Any


class ChatPanel(VerticalScroll):
    """Chat panel with message history."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._chat_log = RichLog(highlight=True, markup=True, wrap=True)
        self._assistant_buffer = ""
        self._in_assistant_message = False

    def compose(self):
        yield self._chat_log

    def add_system_message(self, message: str) -> None:
        """Add a system message."""
        self._chat_log.write(f"[dim italic]{message}[/dim italic]")

    def add_user_message(self, message: str) -> None:
        """Add a user message."""
        self._chat_log.write(f"[bold cyan]You:[/bold cyan] {message}")

    def start_assistant_message(self) -> None:
        """Start a new assistant message."""
        self._in_assistant_message = True
        self._assistant_buffer = ""
        self._chat_log.write("[bold green]Assistant:[/bold green]")

    def append_assistant_content(self, content: str) -> None:
        """Append streaming content to assistant message."""
        self._assistant_buffer += content
        # Update the last line
        # RichLog doesn't support easy in-place update, so we re-render
        # For now, just write the delta
        self._chat_log.write(content)

    def add_tool_call(self, tool_name: str) -> None:
        """Add a tool call indicator."""
        self._chat_log.write(f"[yellow]🔧 {tool_name}...[/yellow]")

    def add_tool_result(self, tool_name: str, result: Any) -> None:
        """Add a tool result."""
        if result.success:
            self._chat_log.write(f"[green]✓ {tool_name}[/green]")
            if result.output:
                # Truncate long output
                output = result.output[:500]
                if len(result.output) > 500:
                    output += "..."
                self._chat_log.write(f"[dim]{output}[/dim]")
        else:
            self._chat_log.write(f"[red]✗ {tool_name}: {result.error}[/red]")

    def clear(self) -> None:
        """Clear chat history."""
        self.log.clear()