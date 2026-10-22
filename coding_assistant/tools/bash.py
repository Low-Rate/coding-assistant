"""Bash execution tool with safety controls."""

import asyncio
import os
import shlex
from pathlib import Path
from typing import Any

from coding_assistant.tools.base import ToolResult, tool


# Commands that are allowed without confirmation
SAFE_COMMANDS = {
    "ls", "cat", "head", "tail", "grep", "rg", "find", "which",
    "python", "python3", "node", "npm", "cargo", "go", "rustc",
    "git", "git status", "git diff", "git log", "git show",
    "echo", "pwd", "date", "whoami", "env", "printenv",
    "ps", "top", "htop", "df", "du", "free",
    "curl", "wget", "jq", "yq",
    "make", "cmake", "ninja",
    "pytest", "cargo test", "go test", "npm test",
}

# Commands that require confirmation
DANGEROUS_COMMANDS = {
    "rm", "rmdir", "mv", "cp", "chmod", "chown", "chgrp",
    "dd", "mkfs", "fdisk", "mount", "umount",
    "kill", "killall", "pkill",
    "shutdown", "reboot", "halt",
    "apt", "apt-get", "yum", "dnf", "pacman", "brew",
    "pip", "pip3", "npm install", "cargo install",
    "git push", "git commit", "git reset", "git rebase",
    "sudo", "su", "doas",
}


def _is_safe_command(command: str) -> bool:
    """Check if command is in safe list."""
    parts = shlex.split(command)
    if not parts:
        return False
    base_cmd = parts[0]
    return base_cmd in SAFE_COMMANDS


def _is_dangerous_command(command: str) -> bool:
    """Check if command is dangerous."""
    parts = shlex.split(command)
    if not parts:
        return False
    base_cmd = parts[0]
    # Check exact match or prefix
    for dangerous in DANGEROUS_COMMANDS:
        if base_cmd == dangerous or command.startswith(dangerous):
            return True
    return False


@tool(description="Execute a bash command", confirm=True)
def bash(command: str, timeout: int = 30, cwd: str | None = None) -> ToolResult:
    """Execute a bash command with safety controls."""
    # Check if command is safe (no confirmation needed)
    safe = _is_safe_command(command)
    dangerous = _is_dangerous_command(command)

    if dangerous:
        return ToolResult(
            success=False,
            error=f"Dangerous command blocked: {command}. Use with explicit confirmation.",
        )

    # For unsafe commands, we still allow but warn
    # The confirm flag in tool decorator handles user confirmation

    try:
        work_dir = Path(cwd).resolve() if cwd else Path.cwd()
        if not work_dir.exists():
            return ToolResult(success=False, error=f"Working directory not found: {cwd}")

        # Run command
        result = asyncio.run(_run_command(command, timeout, work_dir))

        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"

        return ToolResult(
            success=result.returncode == 0,
            output=output if output else "(no output)",
            metadata={
                "command": command,
                "returncode": result.returncode,
                "cwd": str(work_dir),
            },
        )
    except asyncio.TimeoutError:
        return ToolResult(success=False, error=f"Command timed out after {timeout}s")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def _run_command(command: str, timeout: int, cwd: Path) -> asyncio.subprocess.Process:
    """Run command asynchronously."""
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env={**os.environ, "TERM": "dumb"},
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        proc.stdout = stdout.decode("utf-8", errors="replace") if stdout else ""
        proc.stderr = stderr.decode("utf-8", errors="replace") if stderr else ""
        return proc
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise


@tool(description="Run a command in the background (fire and forget)")
def bash_bg(command: str, cwd: str | None = None) -> ToolResult:
    """Start a background process."""
    try:
        work_dir = Path(cwd).resolve() if cwd else Path.cwd()

        proc = asyncio.run(_start_bg(command, work_dir))

        return ToolResult(
            success=True,
            output=f"Started background process (PID: {proc.pid})",
            metadata={"pid": proc.pid, "command": command, "cwd": str(work_dir)},
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def _start_bg(command: str, cwd: Path) -> asyncio.subprocess.Process:
    """Start background process."""
    return await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        cwd=cwd,
        start_new_session=True,
    )