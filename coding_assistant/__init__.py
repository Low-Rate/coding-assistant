"""Coding Assistant - Local-first AI coding assistant with TUI."""

__version__ = "0.1.0"
__author__ = "Claude Code"
__description__ = "Local-first AI coding assistant with TUI, memory, and RAG"

from coding_assistant.config.settings import settings, get_settings

__all__ = ["settings", "get_settings"]