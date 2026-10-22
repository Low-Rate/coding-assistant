"""File operation tools."""

from pathlib import Path
from typing import Any

from coding_assistant.tools.base import ToolResult, tool


@tool(description="Read file contents with optional offset and limit")
def read_file(path: str, offset: int = 0, limit: int = 2000) -> ToolResult:
    """Read a file from the filesystem."""
    try:
        file_path = Path(path).resolve()
        if not file_path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        if not file_path.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")

        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        if offset >= len(lines):
            return ToolResult(success=False, error=f"Offset {offset} exceeds file length {len(lines)}")

        end = min(offset + limit, len(lines))
        selected = lines[offset:end]

        result = "\n".join(f"{i + offset + 1:4d} | {line}" for i, line in enumerate(selected))
        if end < len(lines):
            result += f"\n... ({len(lines) - end} more lines)"

        return ToolResult(
            success=True,
            output=result,
            metadata={"path": str(file_path), "total_lines": len(lines), "offset": offset, "limit": limit},
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tool(description="Write content to a file (creates or overwrites)")
def write_file(path: str, content: str) -> ToolResult:
    """Write content to a file."""
    try:
        file_path = Path(path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if file exists to generate diff
        old_content = ""
        if file_path.exists():
            old_content = file_path.read_text(encoding="utf-8")

        file_path.write_text(content, encoding="utf-8")

        # Generate diff if file existed
        diff = ""
        if old_content:
            diff = _generate_diff(old_content, content, path)

        return ToolResult(
            success=True,
            output=f"Written {len(content)} chars to {path}",
            metadata={"path": str(file_path), "size": len(content), "diff": diff},
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tool(description="Edit a file by replacing old_string with new_string")
def edit_file(path: str, old_string: str, new_string: str) -> ToolResult:
    """Edit a file using exact string replacement."""
    try:
        file_path = Path(path).resolve()
        if not file_path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")

        content = file_path.read_text(encoding="utf-8")
        if old_string not in content:
            return ToolResult(success=False, error="old_string not found in file")

        new_content = content.replace(old_string, new_string, 1)
        file_path.write_text(new_content, encoding="utf-8")

        # Generate diff for display
        diff = _generate_diff(content, new_content, path)

        return ToolResult(
            success=True,
            output=f"Edited {path} (1 replacement)",
            metadata={"path": str(file_path), "diff": diff},
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


def _generate_diff(old_content: str, new_content: str, path: str) -> str:
    """Generate a unified diff between old and new content."""
    import difflib

    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="")
    return "".join(diff)


@tool(description="List directory contents as a tree")
def list_dir(path: str = ".", depth: int = 3, show_hidden: bool = False) -> ToolResult:
    """List directory tree."""
    try:
        root = Path(path).resolve()
        if not root.exists():
            return ToolResult(success=False, error=f"Path not found: {path}")

        lines = []

        def walk(dir_path: Path, prefix: str = "", current_depth: int = 0):
            if current_depth > depth:
                return
            try:
                entries = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            except PermissionError:
                lines.append(f"{prefix}└── [Permission denied]")
                return

            for i, entry in enumerate(entries):
                if not show_hidden and entry.name.startswith("."):
                    continue
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{entry.name}")
                if entry.is_dir():
                    extension = "    " if is_last else "│   "
                    walk(entry, prefix + extension, current_depth + 1)

        lines.insert(0, f"{root.name}/")
        walk(root)

        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"path": str(root), "depth": depth},
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tool(description="Search for pattern in files using regex")
def grep(pattern: str, path: str = ".", glob: str = "**/*", max_results: int = 100) -> ToolResult:
    """Search files with regex pattern."""
    try:
        import re

        root = Path(path).resolve()
        regex = re.compile(pattern)
        matches = []
        files_searched = 0

        for file_path in root.glob(glob):
            if not file_path.is_file():
                continue
            if file_path.stat().st_size > 1_000_000:
                continue

            files_searched += 1
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    matches.append(
                        {
                            "file": str(file_path.relative_to(root)),
                            "line": i,
                            "content": line.strip()[:200],
                        }
                    )
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break

        if not matches:
            return ToolResult(success=True, output="No matches found", metadata={"files_searched": files_searched})

        output_lines = []
        for m in matches:
            output_lines.append(f"{m['file']}:{m['line']}: {m['content']}")

        return ToolResult(
            success=True,
            output="\n".join(output_lines),
            metadata={"matches": len(matches), "files_searched": files_searched},
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tool(description="Find files matching a glob pattern")
def glob_files(pattern: str, path: str = ".") -> ToolResult:
    """Find files matching glob pattern."""
    try:
        root = Path(path).resolve()
        matches = list(root.glob(pattern))
        files = [str(p.relative_to(root)) for p in matches if p.is_file()]
        dirs = [str(p.relative_to(root)) + "/" for p in matches if p.is_dir()]

        output = []
        if dirs:
            output.append("Directories:")
            output.extend(f"  {d}" for d in sorted(dirs))
        if files:
            output.append("Files:")
            output.extend(f"  {f}" for f in sorted(files))

        return ToolResult(
            success=True,
            output="\n".join(output) if output else "No matches",
            metadata={"files": len(files), "dirs": len(dirs)},
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))