"""Codebase indexer using tree-sitter for parsing."""

import hashlib
import os
from pathlib import Path
from typing import Any

import tree_sitter
from tree_sitter_languages import get_language, get_parser

from coding_assistant.config.settings import get_settings
from coding_assistant.memory.vector_store import VectorStore


class CodeIndexer:
    """Indexes codebase files for RAG retrieval."""

    def __init__(self, project_root: str, vector_store: VectorStore | None = None):
        self.settings = get_settings()
        self.project_root = Path(project_root).resolve()
        self.vector_store = vector_store or VectorStore()
        self.parser_cache: dict[str, tree_sitter.Parser] = {}
        self._file_hashes: dict[str, str] = {}
        self._embedding_model = None

    def _get_embedding_model(self):
        """Lazy load embedding model."""
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer(
                self.settings.vector_db.embedding_model,
                device=self.settings.vector_db.embedding_device,
            )
        return self._embedding_model

    def _embed_chunks(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for chunk texts."""
        model = self._get_embedding_model()
        return model.encode(texts).tolist()

    def _get_parser(self, language: str) -> tree_sitter.Parser | None:
        """Get tree-sitter parser for language."""
        if language in self.parser_cache:
            return self.parser_cache[language]

        try:
            parser = get_parser(language)
            self.parser_cache[language] = parser
            return parser
        except Exception:
            return None

    def _get_language_from_path(self, path: Path) -> str | None:
        """Map file extension to tree-sitter language."""
        suffix_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".kt": "kotlin",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "c_sharp",
            ".php": "php",
            ".rb": "ruby",
            ".swift": "swift",
            ".scala": "scala",
            ".clj": "clojure",
        }
        return suffix_map.get(path.suffix.lower())

    def _compute_hash(self, content: str) -> str:
        """Compute content hash."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _should_index(self, path: Path) -> bool:
        """Check if file should be indexed."""
        # Check size
        try:
            if path.stat().st_size > self.settings.indexer.max_file_size:
                return False
        except OSError:
            return False

        # Check excluded patterns
        rel_path = path.relative_to(self.project_root)
        for pattern in self.settings.indexer.excluded_patterns:
            if rel_path.match(pattern):
                return False

        # Check included extensions
        if self.settings.indexer.included_extensions:
            if path.suffix.lower() not in self.settings.indexer.included_extensions:
                return False

        return True

    def _extract_chunks(self, content: str, path: Path, language: str) -> list[dict[str, Any]]:
        """Extract semantic chunks from code using tree-sitter."""
        parser = self._get_parser(language)
        if not parser:
            return self._fallback_chunks(content, path)

        tree = parser.parse(content.encode())
        chunks = []

        # Query for functions, classes, methods
        queries = {
            "python": """
                (function_definition name: (identifier) @name) @function
                (class_definition name: (identifier) @name) @class
                (async_function_definition name: (identifier) @name) @function
            """,
            "javascript": """
                (function_declaration name: (identifier) @name) @function
                (class_declaration name: (identifier) @name) @class
                (method_definition name: (property_identifier) @name) @method
                (arrow_function) @function
            """,
            "typescript": """
                (function_declaration name: (identifier) @name) @function
                (class_declaration name: (type_identifier) @name) @class
                (method_definition name: (property_identifier) @name) @method
            """,
            "rust": """
                (function_item name: (identifier) @name) @function
                (struct_item name: (type_identifier) @name) @struct
                (impl_item) @impl
                (trait_item name: (type_identifier) @name) @trait
            """,
            "go": """
                (function_declaration name: (identifier) @name) @function
                (type_declaration (type_spec name: (type_identifier) @name)) @type
                (method_declaration name: (field_identifier) @name) @method
            """,
        }

        query_str = queries.get(language)
        if not query_str:
            return self._fallback_chunks(content, path)

        try:
            lang = get_language(language)
            query = lang.query(query_str)
            captures = query.captures(tree.root_node)

            for node, capture_name in captures:
                if capture_name in ("function", "class", "method", "struct", "impl", "trait", "type"):
                    # Get the parent node that represents the full definition
                    parent = node.parent
                    while parent and parent.type not in (
                        "function_definition", "class_definition", "async_function_definition",
                        "function_declaration", "class_declaration", "method_definition",
                        "function_item", "struct_item", "impl_item", "trait_item",
                        "type_declaration",
                    ):
                        parent = parent.parent

                    if parent:
                        start = parent.start_point[0]
                        end = parent.end_point[0]
                        chunk_content = "\n".join(content.splitlines()[start:end + 1])

                        if len(chunk_content.strip()) > 20:  # Skip tiny chunks
                            chunks.append({
                                "content": chunk_content,
                                "type": capture_name,
                                "name": content.splitlines()[start].strip()[:100],
                                "start_line": start + 1,
                                "end_line": end + 1,
                            })
        except Exception:
            pass

        # If no semantic chunks found, fall back
        if not chunks:
            return self._fallback_chunks(content, path)

        return chunks

    def _fallback_chunks(self, content: str, path: Path) -> list[dict[str, Any]]:
        """Fallback chunking by lines."""
        lines = content.splitlines()
        chunks = []
        chunk_size = self.settings.indexer.chunk_size
        overlap = self.settings.indexer.chunk_overlap

        for i in range(0, len(lines), chunk_size - overlap):
            chunk_lines = lines[i:i + chunk_size]
            if len(chunk_lines) < 5:  # Skip very small chunks
                continue
            chunk_content = "\n".join(chunk_lines)
            chunks.append({
                "content": chunk_content,
                "type": "chunk",
                "name": f"{path.name}:{i + 1}-{min(i + chunk_size, len(lines))}",
                "start_line": i + 1,
                "end_line": min(i + chunk_size, len(lines)),
            })

        return chunks

    def index_file(self, path: Path) -> int:
        """Index a single file."""
        if not self._should_index(path):
            return 0

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return 0
        except Exception:
            return 0

        # Check if file changed
        file_hash = self._compute_hash(content)
        rel_path = str(path.relative_to(self.project_root))

        if self._file_hashes.get(rel_path) == file_hash:
            return 0  # Unchanged

        self._file_hashes[rel_path] = file_hash

        # Remove old chunks for this file
        self.vector_store.delete_by_metadata({"file_path": rel_path})

        # Extract chunks
        language = self._get_language_from_path(path)
        chunks = self._extract_chunks(content, path, language) if language else self._fallback_chunks(content, path)

        if not chunks:
            return 0

        # Generate embeddings for all chunks
        chunk_texts = [chunk["content"] for chunk in chunks]
        embeddings = self._embed_chunks(chunk_texts)

        ids = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{rel_path}:{i}"
            ids.append(chunk_id)
            documents.append(chunk["content"])
            metadatas.append({
                "file_path": rel_path,
                "chunk_type": chunk["type"],
                "chunk_name": chunk["name"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "language": language or "unknown",
                "hash": file_hash,
            })

        # Store in vector DB with embeddings
        self.vector_store.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

        return len(chunks)

    def index_project(self) -> dict[str, int]:
        """Index entire project."""
        stats = {"files": 0, "chunks": 0, "errors": 0}

        for path in self.project_root.rglob("*"):
            if not path.is_file():
                continue

            try:
                chunks = self.index_file(path)
                if chunks > 0:
                    stats["files"] += 1
                    stats["chunks"] += chunks
            except Exception:
                stats["errors"] += 1

        return stats

    def watch_and_index(self, callback=None) -> None:
        """Watch for file changes and re-index incrementally."""
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class IndexHandler(FileSystemEventHandler):
            def __init__(self, indexer):
                self.indexer = indexer

            def on_modified(self, event):
                if event.is_directory:
                    return
                path = Path(event.src_path)
                if self.indexer._should_index(path):
                    self.indexer.index_file(path)
                    if callback:
                        callback(path)

            def on_created(self, event):
                self.on_modified(event)

            def on_deleted(self, event):
                if event.is_directory:
                    return
                path = Path(event.src_path)
                try:
                    rel_path = str(path.relative_to(self.indexer.project_root))
                    self.indexer.vector_store.delete_by_metadata({"file_path": rel_path})
                except Exception:
                    pass

        observer = Observer()
        handler = IndexHandler(self)
        observer.schedule(handler, str(self.project_root), recursive=True)
        observer.start()

        return observer