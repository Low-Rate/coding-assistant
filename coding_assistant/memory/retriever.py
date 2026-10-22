"""Memory retriever for RAG queries."""

from typing import Any

from coding_assistant.memory.vector_store import VectorStore
from coding_assistant.config.settings import get_settings


class Retriever:
    """Hybrid retriever for code and conversation memory."""

    def __init__(self, vector_store: VectorStore | None = None):
        self.settings = get_settings()
        self.vector_store = vector_store or VectorStore()
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

    def _embed_query(self, query: str) -> list[float]:
        """Generate embedding for query."""
        model = self._get_embedding_model()
        return model.encode(query).tolist()

    def retrieve_code(
        self,
        query: str,
        n_results: int = 5,
        language: str | None = None,
        file_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant code chunks."""
        query_embedding = self._embed_query(query)

        where = {}
        if language:
            where["language"] = language
        if file_path:
            where["file_path"] = file_path

        results = self.vector_store.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where if where else None,
        )

        chunks = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                distance = results["distances"][0][i] if results.get("distances") else 0
                chunks.append({
                    "content": doc,
                    "metadata": metadata,
                    "score": 1 - distance,  # Convert distance to similarity
                })

        return chunks

    def retrieve_conversation(
        self,
        query: str,
        n_results: int = 3,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant conversation history."""
        # This would query a separate conversation collection
        # For now, return empty
        return []

    def hybrid_search(
        self,
        query: str,
        n_results: int = 10,
        code_weight: float = 0.7,
        conversation_weight: float = 0.3,
    ) -> dict[str, list[dict[str, Any]]]:
        """Perform hybrid search across code and conversation."""
        code_results = self.retrieve_code(query, n_results=int(n_results * code_weight))
        conv_results = self.retrieve_conversation(query, n_results=int(n_results * conversation_weight))

        return {
            "code": code_results,
            "conversation": conv_results,
        }

    def get_project_context(self, project_root: str) -> str:
        """Get high-level project context for prompt."""
        # Get file structure summary
        import subprocess
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            files = result.stdout.strip().split("\n") if result.stdout else []
        except Exception:
            files = []

        # Categorize files by extension (handle paths with dots)
        categories = {
            "python": [], "javascript": [], "typescript": [], "rust": [],
            "go": [], "java": [], "other": [],
        }

        ext_map = {
            "py": "python",
            "js": "javascript", "jsx": "javascript",
            "ts": "typescript", "tsx": "typescript",
            "rs": "rust",
            "go": "go",
            "java": "java",
        }

        for f in files[:200]:  # Limit
            # Get extension from filename only (not path)
            import os
            filename = os.path.basename(f)
            ext = filename.split(".")[-1].lower() if "." in filename else "other"
            cat = ext_map.get(ext, "other")
            categories[cat].append(f)

        summary = "Project Structure:\n"
        for cat, cat_files in categories.items():
            if cat_files:
                summary += f"  {cat}: {len(cat_files)} files\n"
                for f in cat_files[:5]:
                    summary += f"    - {f}\n"
                if len(cat_files) > 5:
                    summary += f"    ... and {len(cat_files) - 5} more\n"

        return summary