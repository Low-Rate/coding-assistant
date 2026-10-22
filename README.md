# Coding Assistant

A local-first AI coding assistant with TUI, memory, and RAG capabilities. Runs entirely on your machine via Ollama.

## Features

- **TUI Interface** - Interactive terminal UI built with Textual (like Claude Code)
- **Local Inference** - Powered by Ollama, no data leaves your machine
- **Memory & RAG** - Vector-based code retrieval, conversation history, project context
- **Multi-language** - Python, TypeScript, Rust, Go, and more
- **Git Integration** - Status, diff, commit, log built-in
- **Tool System** - File ops, bash, grep, glob with safety controls

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) installed and running
- A code model pulled: `ollama pull qwen2.5-coder:7b`

### Installation

```bash
# Clone and install
git clone <repo>
cd coding-assistant
pip install -e .[dev]

# Or install from PyPI (when published)
pip install coding-assistant
```

### Usage

```bash
# Start in current directory
coding-assistant run

# Start in specific project
coding-assistant run /path/to/project

# Resume a session
coding-assistant run --session abc123

# Use a different model
coding-assistant run --model deepseek-r1:7b

# Index codebase for RAG
coding-assistant index

# List sessions
coding-assistant sessions

# Manage models
coding-assistant models --list
coding-assistant models --pull qwen2.5-coder:14b
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+Q` | Quit |
| `Ctrl+C` | Cancel current operation |
| `Ctrl+D` | Toggle diff panel |
| `Ctrl+F` | Focus file tree |
| `Ctrl+I` | Focus input |
| `Ctrl+/` | Command palette |
| `Enter` | Send message |
| `Ctrl+Enter` | Newline in input |

## Architecture

```
coding_assistant/
├── cli.py              # CLI entry point (Typer)
├── config/             # Configuration (Pydantic Settings)
├── llm/                # LLM clients (Ollama)
├── agent/              # Core agent logic
│   ├── loop.py         # ReAct agent loop
│   ├── prompt_builder.py # Prompt assembly
│   ├── tool_executor.py  # Tool execution
│   └── session.py      # Session persistence
├── tools/              # Built-in tools
│   ├── base.py         # Tool registry & decorator
│   ├── file_ops.py     # Read/write/edit/list/grep
│   ├── bash.py         # Command execution
│   └── git_tool.py     # Git operations
├── memory/             # Memory & RAG system
│   ├── vector_store.py # ChromaDB wrapper
│   ├── indexer.py      # Tree-sitter code indexer
│   ├── retriever.py    # Hybrid retrieval
│   ├── summarizer.py   # Conversation summarization
│   └── project_context.py # Project analysis
└── tui/                # Terminal UI (Textual)
    ├── app.py          # Main app
    └── panels/         # UI panels (chat, files, diff, status)
```

## Configuration

Config file at `~/.coding-assistant/config.yaml`:

```yaml
ollama:
  host: "http://localhost:11434"
  default_model: "qwen2.5-coder:7b"
  reasoning_model: "deepseek-r1:7b"
  fast_model: "llama3.2:3b"

vector_db:
  persist_directory: "~/.coding-assistant/chroma"
  embedding_model: "sentence-transformers/all-MiniLM-L6-v2"

indexer:
  enabled: true
  chunk_size: 500
  excluded_patterns:
    - "**/.git/**"
    - "**/node_modules/**"
    - "**/target/**"

memory:
  max_conversation_tokens: 8000
  summary_threshold: 6000

tui:
  theme: "dark"
  mouse_support: true
```

## Development

```bash
# Install dev dependencies
pip install -e .[dev]

# Run tests
pytest

# Lint
ruff check .
mypy coding_assistant

# Format
ruff format .
```

## Roadmap

- [ ] Phase 1: MVP - TUI, Ollama chat, basic tools, session persistence
- [ ] Phase 2: Memory - Vector store, code indexing, RAG retrieval, summarization
- [ ] Phase 3: UX - Diff panel, git integration, slash commands, multi-file edits
- [ ] Phase 4: Advanced - LSP integration, plugin system, evaluation harness

## License

MIT