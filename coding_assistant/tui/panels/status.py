"""Status panel for showing model, tokens, and connection status."""

from textual.widgets import Static
from typing import Any


class StatusPanel(Static):
    """Status bar panel."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.backend = "ollama"
        self.model = "Unknown"
        self.status = "ready"
        self.tokens_in = 0
        self.tokens_out = 0
        self.memory_items = 0

    def on_mount(self) -> None:
        """Initialize display."""
        self.update_display()

    def set_backend(self, backend: str) -> None:
        """Set current backend."""
        self.backend = backend
        self.update_display()

    def set_model(self, model: str) -> None:
        """Set current model."""
        self.model = model
        self.update_display()

    def set_status(self, status: str) -> None:
        """Set current status."""
        self.status = status
        self.update_display()

    def update_tokens(self, metadata: dict[str, Any]) -> None:
        """Update token counts from usage metadata."""
        if metadata:
            # Support both Ollama and OpenAI usage formats
            self.tokens_in = metadata.get("prompt_eval_count", 0) or metadata.get("prompt_tokens", 0)
            self.tokens_out = metadata.get("eval_count", 0) or metadata.get("completion_tokens", 0)
        self.update_display()

    def set_memory_count(self, count: int) -> None:
        """Set memory item count."""
        self.memory_items = count
        self.update_display()

    def update_display(self) -> None:
        """Update the status display."""
        status_icons = {
            "ready": "🟢",
            "thinking": "🟡",
            "tool_running": "🔵",
            "error": "🔴",
        }
        icon = status_icons.get(self.status, "⚪")
        backend_label = "Ollama" if self.backend == "ollama" else "LiteLLM"

        self.update(
            f"{icon} {backend_label}: {self.model} | "
            f"Tokens: {self.tokens_in}→{self.tokens_out} | "
            f"Memory: {self.memory_items} | "
            f"Status: {self.status}"
        )