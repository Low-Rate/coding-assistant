"""Project context extraction and management."""

from pathlib import Path
from typing import Any
import json

from coding_assistant.memory.vector_store import VectorStore
from coding_assistant.config.settings import get_settings


class ProjectContext:
    """Manages project-level context knowledge."""

    def __init__(self, project_root: str, vector_store: VectorStore | None = None):
        self.settings = get_settings()
        self.project_root = Path(project_root).resolve()
        self.vector_store = vector_store or VectorStore()
        self._context_cache: dict[str, Any] = {}

    def extract_context(self) -> dict[str, Any]:
        """Extract high-level project context."""
        context = {
            "structure": self._get_structure(),
            "conventions": self._detect_conventions(),
            "dependencies": self._get_dependencies(),
            "entry_points": self._find_entry_points(),
            "test_patterns": self._find_test_patterns(),
        }
        self._context_cache = context
        return context

    def _get_structure(self) -> dict[str, Any]:
        """Get project directory structure."""
        structure = {"dirs": [], "files_by_ext": {}}

        for path in self.project_root.rglob("*"):
            if path.is_dir():
                rel = path.relative_to(self.project_root)
                if not any(part.startswith(".") for part in rel.parts):
                    if len(rel.parts) <= 3:  # Limit depth
                        structure["dirs"].append(str(rel))
            elif path.is_file():
                ext = path.suffix.lower()
                if ext:
                    structure["files_by_ext"][ext] = structure["files_by_ext"].get(ext, 0) + 1

        return structure

    def _detect_conventions(self) -> dict[str, Any]:
        """Detect code conventions from existing files."""
        conventions = {
            "indent": "spaces",
            "indent_size": 4,
            "line_length": 100,
            "naming": {},
            "patterns": [],
        }

        # Check Python files for conventions
        py_files = list(self.project_root.rglob("*.py"))[:20]
        if py_files:
            import re
            for f in py_files:
                try:
                    content = f.read_text(encoding="utf-8")
                    # Detect indent
                    if "    " in content[:500] and "\t" not in content[:500]:
                        conventions["indent"] = "spaces"
                        # Count leading spaces
                        for line in content.splitlines()[:50]:
                            match = re.match(r"^( +)", line)
                            if match and len(match.group(1)) % 4 == 0 and len(match.group(1)) > 0:
                                conventions["indent_size"] = len(match.group(1))
                                break
                except Exception:
                    pass

        # Check for common patterns
        if (self.project_root / "pyproject.toml").exists():
            conventions["patterns"].append("pyproject.toml config")
        if (self.project_root / "Cargo.toml").exists():
            conventions["patterns"].append("Rust Cargo project")
        if (self.project_root / "package.json").exists():
            conventions["patterns"].append("Node.js project")
        if (self.project_root / "go.mod").exists():
            conventions["patterns"].append("Go module")

        return conventions

    def _get_dependencies(self) -> dict[str, list[str]]:
        """Extract project dependencies."""
        deps = {"python": [], "javascript": [], "rust": [], "go": []}

        # Python
        for f in ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]:
            path = self.project_root / f
            if path.exists():
                try:
                    content = path.read_text()
                    if f == "requirements.txt":
                        deps["python"] = [
                            line.split("==")[0].split(">=")[0].split("<=")[0].strip()
                            for line in content.splitlines()
                            if line.strip() and not line.startswith("#")
                        ]
                    elif f == "pyproject.toml":
                        # Simple extraction
                        import re
                        matches = re.findall(r'"([^"]+)"', content)
                        deps["python"] = [m for m in matches if not m.startswith(".")]
                except Exception:
                    pass

        # Node.js
        pkg = self.project_root / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                deps["javascript"] = list(data.get("dependencies", {}).keys()) + \
                                   list(data.get("devDependencies", {}).keys())
            except Exception:
                pass

        # Rust
        cargo = self.project_root / "Cargo.toml"
        if cargo.exists():
            try:
                content = cargo.read_text()
                import re
                deps["rust"] = re.findall(r'^(\w+)\s*=', content, re.MULTILINE)
            except Exception:
                pass

        # Go
        gomod = self.project_root / "go.mod"
        if gomod.exists():
            try:
                content = gomod.read_text()
                for line in content.splitlines():
                    if line.strip().startswith("require"):
                        parts = line.split()
                        if len(parts) >= 2:
                            deps["go"].append(parts[1])
            except Exception:
                pass

        return deps

    def _find_entry_points(self) -> list[str]:
        """Find likely entry points."""
        entry_points = []

        patterns = [
            "main.py", "__main__.py", "cli.py", "app.py", "run.py",
            "main.rs", "lib.rs",
            "main.go", "cmd/main.go",
            "index.js", "index.ts", "main.js", "main.ts",
            "App.java", "Main.java",
            "Program.cs",
        ]

        for pattern in patterns:
            for path in self.project_root.rglob(pattern):
                rel = path.relative_to(self.project_root)
                entry_points.append(str(rel))

        return entry_points[:10]

    def _find_test_patterns(self) -> dict[str, Any]:
        """Find test file patterns."""
        patterns = {
            "frameworks": [],
            "locations": [],
            "naming": [],
        }

        test_files = list(self.project_root.rglob("*test*.py")) + \
                     list(self.project_root.rglob("*_test.py")) + \
                     list(self.project_root.rglob("test_*.py"))

        if test_files:
            patterns["locations"] = [str(f.relative_to(self.project_root)) for f in test_files[:10]]
            # Check for pytest
            for f in test_files[:5]:
                try:
                    content = f.read_text()
                    if "pytest" in content or "import pytest" in content:
                        patterns["frameworks"].append("pytest")
                        break
                    if "unittest" in content:
                        patterns["frameworks"].append("unittest")
                except Exception:
                    pass

        # Check for other test patterns
        for path in self.project_root.rglob("*"):
            if path.is_dir() and path.name in ("tests", "test", "__tests__", "spec"):
                patterns["locations"].append(str(path.relative_to(self.project_root)))

        return patterns

    def format_for_prompt(self) -> str:
        """Format context for inclusion in system prompt."""
        if not self._context_cache:
            self.extract_context()

        ctx = self._context_cache
        lines = ["## Project Context"]

        # Structure
        struct = ctx.get("structure", {})
        if struct.get("files_by_ext"):
            lines.append("\n### File Types")
            for ext, count in sorted(struct["files_by_ext"].items(), key=lambda x: -x[1])[:10]:
                lines.append(f"  {ext}: {count} files")

        # Conventions
        conv = ctx.get("conventions", {})
        if conv.get("patterns"):
            lines.append("\n### Detected Patterns")
            for p in conv["patterns"]:
                lines.append(f"  - {p}")

        # Dependencies
        deps = ctx.get("dependencies", {})
        for lang, lang_deps in deps.items():
            if lang_deps:
                lines.append(f"\n### {lang.title()} Dependencies")
                for d in lang_deps[:10]:
                    lines.append(f"  - {d}")
                if len(lang_deps) > 10:
                    lines.append(f"  ... and {len(lang_deps) - 10} more")

        # Entry points
        eps = ctx.get("entry_points", [])
        if eps:
            lines.append("\n### Entry Points")
            for ep in eps[:5]:
                lines.append(f"  - {ep}")

        return "\n".join(lines)