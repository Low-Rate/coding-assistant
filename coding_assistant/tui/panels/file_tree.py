"""File tree panel for project navigation."""

from pathlib import Path
from textual.widgets import Tree, DirectoryTree
from textual.widgets.tree import TreeNode
from textual.message import Message
from typing import Any


class FileTreePanel(DirectoryTree):
    """File tree panel with git status indicators."""

    def __init__(self, path: str, **kwargs):
        super().__init__(path, **kwargs)
        self.project_root = Path(path).resolve()
        self.show_root = True
        self.show_hidden = False

    def on_mount(self) -> None:
        """Initialize tree."""
        self.root.expand()

    def filter_paths(self, paths: list[Path]) -> list[Path]:
        """Filter paths to exclude unwanted directories."""
        excluded = {
            ".git", "__pycache__", "node_modules", "target", "build",
            "dist", ".venv", "venv", ".env", ".idea", ".vscode",
        }
        return [p for p in paths if p.name not in excluded and not p.name.startswith(".")]

    def get_node_label(self, path: Path) -> str:
        """Get label for a tree node with git status."""
        try:
            import git
            repo = git.Repo(self.project_root, search_parent_directories=True)
            rel_path = path.relative_to(self.project_root)
            status = repo.git.status("--porcelain", str(rel_path))
            if status:
                code = status[:2].strip()
                icons = {
                    "M": "[MD]",  # Modified
                    "A": "➕",  # Added
                    "D": "🗑️",  # Deleted
                    "R": "🔀",  # Renamed
                    "??": "❓", # Untracked
                }
                icon = icons.get(code, "●")
                return f"{icon} {path.name}"
        except Exception:
            pass
        return path.name

    def render_label(self, node: TreeNode, base_style: str, style: str) -> str:
        """Custom label rendering."""
        label = node._label
        if hasattr(node, "_path"):
            label = self.get_node_label(node._path)
        return super().render_label(node, base_style, style)

    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle file selection."""
        node = event.node
        if hasattr(node, "_path") and node._path.is_file():
            # Emit event for opening file
            self.post_message(self.FileSelected(node._path))

    class FileSelected(Message):
        """File selected message."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path


class SimpleFileTree(Tree):
    """Simpler file tree without DirectoryTree auto-loading."""

    def __init__(self, path: str, **kwargs):
        super().__init__("[DIR] " + Path(path).name, **kwargs)
        self.project_root = Path(path).resolve()
        self._build_tree(self.root, self.project_root)

    def _build_tree(self, node: TreeNode, path: Path, depth: int = 0) -> None:
        """Recursively build tree."""
        if depth > 5:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith(".") and entry.name not in {".gitignore", ".env"}:
                continue

            if entry.is_dir():
                child = node.add(f"[DIR] {entry.name}", data={"path": entry, "is_dir": True})
                child.expand()  # Auto-expand first level
                if depth < 2:
                    self._build_tree(child, entry, depth + 1)
            else:
                icon = self._get_file_icon(entry)
                node.add(f"{icon} {entry.name}", data={"path": entry, "is_dir": False})

    def _get_file_icon(self, path: Path) -> str:
        """Get icon for file type."""
        suffix = path.suffix.lower()
        icons = {
            ".py": "[PY]", ".js": "[JS]", ".ts": "[TS]", ".tsx": "[REACT]", ".jsx": "[REACT]",
            ".rs": "[RS]", ".go": "[GO]", ".java": "[JAVA]", ".kt": "[KT]",
            ".cpp": "[CFG]", ".cc": "[CFG]", ".c": "[CFG]", ".h": "[HDR]",
            ".cs": "[CS]", ".php": "[PHP]", ".rb": "[RB]", ".swift": "[SWIFT]",
            ".md": "[MD]", ".txt": "[TXT]", ".json": "[JSON]", ".yaml": "[CFG]", ".yml": "[CFG]",
            ".toml": "[CFG]", ".ini": "[CFG]", ".cfg": "[CFG]",
            ".sh": "[SH]", ".bash": "[SH]", ".zsh": "[SH]",
            ".dockerfile": "[DOCKER]", ".sql": "[SQL]",
            ".html": "[HTML]", ".css": "[CSS]", ".scss": "[CSS]",
            ".graphql": "[GQL]", ".proto": "[PROTO]",
        }
        return icons.get(suffix, "[TXT]")