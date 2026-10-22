"""Session management for persistence and checkpoints."""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from coding_assistant.config.settings import get_settings


@dataclass
class Message:
    """Conversation message."""

    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    token_count: int = 0


@dataclass
class Checkpoint:
    """Session checkpoint."""

    id: str
    name: str
    messages: list[Message]
    working_dir: str
    active_files: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Session:
    """A coding assistant session."""

    id: str
    project_root: str
    working_dir: str
    messages: list[Message] = field(default_factory=list)
    active_files: list[str] = field(default_factory=list)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """Manages session persistence."""

    def __init__(self, data_dir: Path | None = None):
        self.settings = get_settings()
        self.data_dir = data_dir or self.settings.data_dir / "sessions"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: Session | None = None

    def create_session(self, project_root: str, working_dir: str | None = None) -> Session:
        """Create a new session."""
        session = Session(
            id=str(uuid.uuid4())[:8],
            project_root=project_root,
            working_dir=working_dir or project_root,
        )
        self._current_session = session
        return session

    def load_session(self, session_id: str) -> Session | None:
        """Load a session from disk."""
        path = self.data_dir / f"{session_id}.json"
        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)

        session = Session(
            id=data["id"],
            project_root=data["project_root"],
            working_dir=data["working_dir"],
            messages=[Message(**m) for m in data.get("messages", [])],
            active_files=data.get("active_files", []),
            checkpoints=[Checkpoint(**c) for c in data.get("checkpoints", [])],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
        )
        self._current_session = session
        return session

    def save_session(self, session: Session | None = None) -> None:
        """Save session to disk."""
        session = session or self._current_session
        if not session:
            return

        session.updated_at = datetime.now().isoformat()
        path = self.data_dir / f"{session.id}.json"

        data = asdict(session)
        # Convert messages and checkpoints
        data["messages"] = [asdict(m) for m in session.messages]
        data["checkpoints"] = [asdict(c) for c in session.checkpoints]

        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def list_sessions(self, project_root: str | None = None) -> list[Session]:
        """List all sessions, optionally filtered by project."""
        sessions = []
        for path in self.data_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                if project_root and data.get("project_root") != project_root:
                    continue
                session = Session(
                    id=data["id"],
                    project_root=data["project_root"],
                    working_dir=data["working_dir"],
                    messages=[Message(**m) for m in data.get("messages", [])],
                    active_files=data.get("active_files", []),
                    checkpoints=[Checkpoint(**c) for c in data.get("checkpoints", [])],
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                    metadata=data.get("metadata", {}),
                )
                sessions.append(session)
            except Exception:
                continue

        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)

    def create_checkpoint(self, name: str, session: Session | None = None) -> Checkpoint:
        """Create a checkpoint of current session state."""
        session = session or self._current_session
        if not session:
            raise ValueError("No active session")

        checkpoint = Checkpoint(
            id=str(uuid.uuid4())[:8],
            name=name,
            messages=session.messages.copy(),
            working_dir=session.working_dir,
            active_files=session.active_files.copy(),
        )
        session.checkpoints.append(checkpoint)
        self.save_session(session)
        return checkpoint

    def restore_checkpoint(self, checkpoint_id: str, session: Session | None = None) -> Session | None:
        """Restore session from a checkpoint."""
        session = session or self._current_session
        if not session:
            return None

        checkpoint = next((c for c in session.checkpoints if c.id == checkpoint_id), None)
        if not checkpoint:
            return None

        session.messages = checkpoint.messages.copy()
        session.working_dir = checkpoint.working_dir
        session.active_files = checkpoint.active_files.copy()
        self.save_session(session)
        return session

    def add_message(self, message: Message, session: Session | None = None) -> None:
        """Add a message to the current session."""
        session = session or self._current_session
        if not session:
            return
        session.messages.append(message)
        self.save_session(session)

    def get_conversation_history(self, session: Session | None = None, limit: int = 50) -> list[Message]:
        """Get recent conversation history."""
        session = session or self._current_session
        if not session:
            return []
        return session.messages[-limit:]

    @property
    def current_session(self) -> Session | None:
        return self._current_session