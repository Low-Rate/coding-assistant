"""TUI panels package."""

from coding_assistant.tui.panels.chat import ChatPanel
from coding_assistant.tui.panels.file_tree import FileTreePanel, SimpleFileTree
from coding_assistant.tui.panels.diff import DiffPanel
from coding_assistant.tui.panels.status import StatusPanel

__all__ = [
    "ChatPanel",
    "FileTreePanel",
    "SimpleFileTree",
    "DiffPanel",
    "StatusPanel",
]