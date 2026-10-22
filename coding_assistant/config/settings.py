"""Configuration management using Pydantic Settings."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OllamaSettings(BaseSettings):
    """Ollama connection settings."""

    model_config = SettingsConfigDict(env_prefix="OLLAMA_")

    host: str = "http://localhost:11434"
    timeout: float = 120.0
    default_model: str = "qwen2.5-coder:7b"
    reasoning_model: str = "deepseek-r1:7b"
    fast_model: str = "llama3.2:3b"


class LiteLLMSettings(BaseSettings):
    """LiteLLM proxy settings (OpenAI-compatible)."""

    model_config = SettingsConfigDict(env_prefix="LITELLM_")

    # Base URL for LiteLLM proxy (e.g., http://localhost:4000 or https://your-proxy.com)
    base_url: str = "http://localhost:4000"
    # API key for LiteLLM proxy (if authentication enabled)
    api_key: str | None = None
    timeout: float = 120.0
    # Model names (LiteLLM uses model names like "gpt-4", "claude-3-opus", etc.)
    default_model: str = "gpt-4o-mini"
    reasoning_model: str = "o1-preview"
    fast_model: str = "gpt-4o-mini"
    # Embedding model
    embedding_model: str = "text-embedding-3-small"
    # Optional: custom headers
    extra_headers: dict[str, str] = Field(default_factory=dict)


class VectorDBSettings(BaseSettings):
    """Vector database (ChromaDB) settings."""

    model_config = SettingsConfigDict(env_prefix="VECTOR_")

    persist_directory: Path = Path.home() / ".coding-assistant" / "chroma"
    collection_name: str = "codebase"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: Literal["cpu", "cuda", "mps"] = "cpu"


class IndexerSettings(BaseSettings):
    """Codebase indexer settings."""

    model_config = SettingsConfigDict(env_prefix="INDEXER_")

    enabled: bool = True
    watch_interval: float = 1.0
    max_file_size: int = 1_000_000  # 1MB
    chunk_size: int = 500
    chunk_overlap: int = 50
    excluded_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/.git/**",
            "**/__pycache__/**",
            "**/node_modules/**",
            "**/target/**",
            "**/build/**",
            "**/dist/**",
            "**/*.lock",
            "**/*.min.js",
            "**/*.min.css",
        ]
    )
    included_extensions: list[str] = Field(
        default_factory=lambda: [
            ".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go",
            ".java", ".kt", ".cpp", ".cc", ".c", ".h", ".hpp",
            ".cs", ".php", ".rb", ".swift", ".scala", ".clj",
            ".md", ".mdx", ".txt", ".json", ".yaml", ".yml",
            ".toml", ".ini", ".cfg", ".conf", ".sh", ".bash",
            ".dockerfile", ".sql", ".graphql", ".proto",
        ]
    )


class MemorySettings(BaseSettings):
    """Memory system settings."""

    model_config = SettingsConfigDict(env_prefix="MEMORY_")

    max_conversation_tokens: int = 8000
    summary_threshold: int = 6000
    summary_model: str = "llama3.2:3b"
    max_history_messages: int = 50
    project_context_tokens: int = 2000


class TUISettings(BaseSettings):
    """TUI settings."""

    model_config = SettingsConfigDict(env_prefix="TUI_")

    theme: Literal["dark", "light", "system"] = "dark"
    show_line_numbers: bool = True
    mouse_support: bool = True
    animation_duration: float = 0.15


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # LLM Backend selection: "ollama" or "litellm"
    llm_backend: Literal["ollama", "litellm"] = "ollama"

    # Sub-settings
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    litellm: LiteLLMSettings = Field(default_factory=LiteLLMSettings)
    vector_db: VectorDBSettings = Field(default_factory=VectorDBSettings)
    indexer: IndexerSettings = Field(default_factory=IndexerSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    tui: TUISettings = Field(default_factory=TUISettings)

    # General
    data_dir: Path = Path.home() / ".coding-assistant"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    auto_index_on_startup: bool = True
    confirm_destructive_tools: bool = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings