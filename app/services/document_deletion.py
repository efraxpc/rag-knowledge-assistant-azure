"""Borrado lógico de documentos conservando sus chunks en el índice."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.exceptions import ApplicationError
from app.rag.contracts import TextChunkStore


@dataclass(frozen=True)
class DocumentDeletionResult:
    document_id: str
    soft_deleted_chunks: int


def utc_now() -> datetime:
    return datetime.now(UTC)


class DocumentDeletionService:
    def __init__(
        self,
        store: TextChunkStore,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._store = store
        self._clock = clock

    def delete(self, document_id: str) -> DocumentDeletionResult:
        deleted_chunks = self._store.soft_delete_document(
            document_id, deleted_at=self._clock()
        )
        if deleted_chunks is None:
            raise ApplicationError(
                "No se encontró el documento solicitado.",
                status_code=404,
                code="document_not_found",
            )
        return DocumentDeletionResult(document_id, deleted_chunks)
