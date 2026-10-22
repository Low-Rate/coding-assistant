"""Vector store wrapper for ChromaDB."""

import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import Any

from coding_assistant.config.settings import get_settings


class VectorStore:
    """Wrapper around ChromaDB for code embeddings."""

    def __init__(self, persist_directory: str | None = None, collection_name: str | None = None):
        self.settings = get_settings()
        self.persist_directory = persist_directory or str(self.settings.vector_db.persist_directory)
        self.collection_name = collection_name or self.settings.vector_db.collection_name

        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add documents to the vector store."""
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas or [{}] * len(ids),
        )

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query the vector store."""
        return self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=["documents", "metadatas", "distances"],
        )

    def delete(self, ids: list[str]) -> None:
        """Delete documents by ID."""
        self.collection.delete(ids=ids)

    def delete_by_metadata(self, where: dict[str, Any]) -> None:
        """Delete documents by metadata filter."""
        self.collection.delete(where=where)

    def get(self, ids: list[str] | None = None, where: dict[str, Any] | None = None) -> dict[str, Any]:
        """Get documents by ID or metadata filter."""
        return self.collection.get(ids=ids, where=where, include=["documents", "metadatas"])

    def count(self) -> int:
        """Get collection count."""
        return self.collection.count()

    def reset(self) -> None:
        """Delete and recreate collection."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )