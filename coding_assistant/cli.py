"""CLI entry point for the coding assistant."""

import typer
from pathlib import Path
from typing import Optional

from coding_assistant.tui.app import CodingAssistantApp
from coding_assistant.agent.session import SessionManager
from coding_assistant.config.settings import get_settings


app = typer.Typer(
    name="coding-assistant",
    help="Local-first AI coding assistant with TUI (Ollama + LiteLLM)",
    add_completion=False,
)


@app.command()
def run(
    project: str = typer.Argument(".", help="Project root directory"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Resume session ID"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    backend: Optional[str] = typer.Option(None, "--backend", "-b", help="LLM backend: ollama or litellm"),
):
    """Start the TUI coding assistant."""
    project_path = Path(project).resolve()

    if not project_path.exists():
        typer.echo(f"Error: Project path does not exist: {project_path}", err=True)
        raise typer.Exit(1)

    # Load or create session
    session_manager = SessionManager()
    session = None

    if session_id:
        session = session_manager.load_session(session_id)
        if not session:
            typer.echo(f"Error: Session not found: {session_id}", err=True)
            raise typer.Exit(1)
    else:
        # Try to find existing session for this project
        sessions = session_manager.list_sessions(str(project_path))
        if sessions:
            session = sessions[0]
            typer.echo(f"Resuming session: {session.id}")

    # Override settings if specified
    settings = get_settings()
    if backend:
        if backend not in ("ollama", "litellm"):
            typer.echo(f"Error: Invalid backend: {backend}. Use 'ollama' or 'litellm'", err=True)
            raise typer.Exit(1)
        settings.llm_backend = backend

    if model:
        if settings.llm_backend == "litellm":
            settings.litellm.default_model = model
        else:
            settings.ollama.default_model = model

    # Run TUI app
    tui_app = CodingAssistantApp(str(project_path), session)
    tui_app.run()


@app.command()
def sessions(
    project: str = typer.Argument(".", help="Project root directory"),
):
    """List sessions for a project."""
    project_path = Path(project).resolve()
    session_manager = SessionManager()
    sessions = session_manager.list_sessions(str(project_path))

    if not sessions:
        typer.echo("No sessions found.")
        return

    typer.echo(f"Sessions for {project_path}:")
    for s in sessions:
        msg_count = len(s.messages)
        typer.echo(f"  {s.id} - {msg_count} messages - {s.updated_at[:19]}")


@app.command()
def index(
    project: str = typer.Argument(".", help="Project root directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-index all files"),
):
    """Index project codebase for RAG."""
    from coding_assistant.memory.indexer import CodeIndexer
    from coding_assistant.memory.vector_store import VectorStore

    project_path = Path(project).resolve()
    typer.echo(f"Indexing {project_path}...")

    vector_store = VectorStore()
    if force:
        vector_store.reset()

    indexer = CodeIndexer(str(project_path), vector_store)
    stats = indexer.index_project()

    typer.echo(f"Indexed: {stats['files']} files, {stats['chunks']} chunks, {stats['errors']} errors")


@app.command()
def models(
    list_models: bool = typer.Option(True, "--list", "-l", help="List available models"),
    pull: Optional[str] = typer.Option(None, "--pull", help="Pull a model (Ollama only)"),
    backend: Optional[str] = typer.Option(None, "--backend", "-b", help="Backend: ollama or litellm"),
):
    """Manage models."""
    import asyncio
    settings = get_settings()

    # Use specified backend or current setting
    target_backend = backend or settings.llm_backend

    async def _run():
        if target_backend == "litellm":
            from coding_assistant.llm.litellm import LiteLLMClient, get_available_models
            if pull:
                typer.echo("Pull not supported for LiteLLM. Models are configured in LiteLLM proxy.")
                return
            if list_models:
                models = await get_available_models()
                typer.echo(f"Available models (LiteLLM):")
                for m in models:
                    typer.echo(f"  {m}")
        else:
            from coding_assistant.llm.ollama import OllamaClient, get_available_models, ensure_model_available
            if pull:
                typer.echo(f"Pulling {pull}...")
                async with OllamaClient() as client:
                    async for progress in client.pull_model(pull):
                        if "status" in progress:
                            typer.echo(f"  {progress['status']}")
                typer.echo("Done!")
                return
            if list_models:
                models = await get_available_models()
                typer.echo(f"Available models (Ollama):")
                for m in models:
                    typer.echo(f"  {m}")

    asyncio.run(_run())


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current config"),
    edit: bool = typer.Option(False, "--edit", help="Edit config file"),
):
    """Manage configuration."""
    settings = get_settings()

    if show:
        typer.echo(settings.model_dump_json(indent=2))
        return

    if edit:
        import subprocess
        config_path = Path.home() / ".coding-assistant" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if not config_path.exists():
            config_path.write_text(settings.model_dump_yaml())
        subprocess.run(["code", str(config_path)])  # or use $EDITOR
        return

    typer.echo("Use --show to view config or --edit to modify.")


@app.command()
def backend(
    name: str = typer.Argument(..., help="Backend name: ollama or litellm"),
):
    """Set default LLM backend."""
    settings = get_settings()
    if name not in ("ollama", "litellm"):
        typer.echo(f"Error: Invalid backend: {name}. Use 'ollama' or 'litellm'", err=True)
        raise typer.Exit(1)
    settings.llm_backend = name
    # Save to config file
    import yaml
    config_path = Path.home() / ".coding-assistant" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    # Convert Path objects to strings for YAML serialization
    data = settings.model_dump()
    def convert_paths(obj):
        if isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: convert_paths(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_paths(v) for v in obj]
        return obj
    config_path.write_text(yaml.dump(convert_paths(data), allow_unicode=True))
    typer.echo(f"Default backend set to: {name}")


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()