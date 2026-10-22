"""Diff panel for showing proposed changes."""

from textual.widgets import Static, RichLog
from textual.containers import Vertical
from typing import Any


class DiffPanel(Vertical):
    """Diff panel showing proposed file changes."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._diff_log = RichLog(highlight=True, markup=True, wrap=True)
        self.current_diff = ""

    def compose(self):
        yield self._diff_log

    def show_diff(self, diff: str) -> None:
        """Display a diff."""
        self.current_diff = diff
        self._diff_log.clear()
        if diff:
            self._diff_log.write(self._format_diff(diff))
        else:
            self._diff_log.write("[dim]No changes[/dim]")

    def _format_diff(self, diff: str) -> str:
        """Format diff with colors."""
        lines = diff.splitlines()
        formatted = []
        for line in lines:
            if line.startswith("+++") or line.startswith("---"):
                formatted.append(f"[bold]{line}[/bold]")
            elif line.startswith("+"):
                formatted.append(f"[green]{line}[/green]")
            elif line.startswith("-"):
                formatted.append(f"[red]{line}[/red]")
            elif line.startswith("@@"):
                formatted.append(f"[cyan]{line}[/cyan]")
            else:
                formatted.append(line)
        return "\n".join(formatted)

    def clear(self) -> None:
        """Clear diff."""
        self.current_diff = ""
        self._diff_log.clear()
        self._diff_log.write("[dim]No changes[/dim]")