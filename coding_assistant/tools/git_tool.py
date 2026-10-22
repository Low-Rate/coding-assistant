"""Git tools for version control integration."""

from pathlib import Path
from typing import Any

from coding_assistant.tools.base import ToolResult, tool


@tool(description="Get git status of working tree")
def git_status(path: str = ".", short: bool = True) -> ToolResult:
    """Show git status."""
    try:
        import git

        repo = git.Repo(Path(path).resolve(), search_parent_directories=True)
        if short:
            status = repo.git.status(short=True)
        else:
            status = repo.git.status()

        return ToolResult(
            success=True,
            output=status if status else "Working tree clean",
            metadata={"repo_root": repo.working_tree_dir},
        )
    except git.InvalidGitRepositoryError:
        return ToolResult(success=False, error="Not a git repository")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tool(description="Show git diff")
def git_diff(path: str = ".", staged: bool = False, file: str | None = None) -> ToolResult:
    """Show git diff."""
    try:
        import git

        repo = git.Repo(Path(path).resolve(), search_parent_directories=True)

        if file:
            diff = repo.git.diff("--cached" if staged else "", file)
        else:
            diff = repo.git.diff("--cached" if staged else "")

        return ToolResult(
            success=True,
            output=diff if diff else "No changes",
            metadata={"repo_root": repo.working_tree_dir, "staged": staged},
        )
    except git.InvalidGitRepositoryError:
        return ToolResult(success=False, error="Not a git repository")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tool(description="Show git log")
def git_log(path: str = ".", max_count: int = 10, oneline: bool = True) -> ToolResult:
    """Show git commit history."""
    try:
        import git

        repo = git.Repo(Path(path).resolve(), search_parent_directories=True)

        args = ["--max-count", str(max_count)]
        if oneline:
            args.append("--oneline")

        log = repo.git.log(*args)

        return ToolResult(
            success=True,
            output=log,
            metadata={"repo_root": repo.working_tree_dir, "count": max_count},
        )
    except git.InvalidGitRepositoryError:
        return ToolResult(success=False, error="Not a git repository")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tool(description="Stage files for commit")
def git_add(path: str = ".", files: list[str] | None = None) -> ToolResult:
    """Stage files for commit."""
    try:
        import git

        repo = git.Repo(Path(path).resolve(), search_parent_directories=True)

        if files:
            repo.index.add(files)
            output = f"Staged: {', '.join(files)}"
        else:
            repo.index.add("*")
            output = "Staged all changes"

        return ToolResult(
            success=True,
            output=output,
            metadata={"repo_root": repo.working_tree_dir},
        )
    except git.InvalidGitRepositoryError:
        return ToolResult(success=False, error="Not a git repository")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tool(description="Create a git commit")
def git_commit(path: str = ".", message: str = "", amend: bool = False) -> ToolResult:
    """Create a git commit."""
    try:
        import git

        repo = git.Repo(Path(path).resolve(), search_parent_directories=True)

        if not message:
            return ToolResult(success=False, error="Commit message required")

        kwargs = {"message": message}
        if amend:
            kwargs["amend"] = True

        commit = repo.index.commit(**kwargs)

        return ToolResult(
            success=True,
            output=f"Committed {commit.hexsha[:8]}: {message.splitlines()[0]}",
            metadata={"commit_hash": commit.hexsha, "message": message},
        )
    except git.InvalidGitRepositoryError:
        return ToolResult(success=False, error="Not a git repository")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tool(description="Show git branch info")
def git_branch(path: str = ".", all_branches: bool = False) -> ToolResult:
    """Show git branches."""
    try:
        import git

        repo = git.Repo(Path(path).resolve(), search_parent_directories=True)

        branches = []
        current = repo.active_branch.name

        for branch in repo.branches:
            prefix = "* " if branch.name == current else "  "
            branches.append(f"{prefix}{branch.name}")

        if all_branches:
            for ref in repo.refs:
                if isinstance(ref, git.RemoteReference):
                    branches.append(f"  remotes/{ref.name}")

        return ToolResult(
            success=True,
            output="\n".join(branches),
            metadata={"current": current, "repo_root": repo.working_tree_dir},
        )
    except git.InvalidGitRepositoryError:
        return ToolResult(success=False, error="Not a git repository")
    except Exception as e:
        return ToolResult(success=False, error=str(e))