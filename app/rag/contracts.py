"""Operaciones requeridas por el RAG, sin tipos del SDK de Azure."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.rag.models import (
    Chunk,
    DocumentSummary,
    EmbeddedChunk,
    SearchHit,
    TextQuery,
    VectorQuery,
)


class TextChunkStore(Protocol):
    def list_documents(self) -> list[DocumentSummary]:
        """Lista documentos guardados y cuenta sus fragmentos indexados."""
        ...

    def index_chunks(self, chunks: Sequence[Chunk]) -> None:
        """Inserta o reemplaza fragmentos de texto sin embeddings."""
        ...

    def soft_delete_document(
        self, document_id: str, *, deleted_at: datetime
    ) -> int | None:
        """Marca los fragmentos del documento y devuelve cuántos cambió."""
        ...

    def search(self, query: TextQuery) -> list[SearchHit]:
        """Recupera fragmentos mediante la pregunta en lenguaje natural."""
        ...


class VectorStore(Protocol):
    def index_chunks(self, chunks: Sequence[EmbeddedChunk]) -> None:
        """Inserta o reemplaza chunks identificados por documento e ID."""
        ...

    def search(self, query: VectorQuery) -> list[SearchHit]:
        """Recupera chunks relevantes, sin exponer detalles del proveedor."""
        ...


class TextCompletionClient(Protocol):
    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Genera texto a partir de mensajes independientes del proveedor."""
        ...
