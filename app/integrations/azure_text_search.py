"""Indexación de texto sin requerir campos vectoriales."""

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from azure.core.exceptions import AzureError
from azure.search.documents import SearchClient
from pydantic import ValidationError

from app.core.exceptions import (
    ApplicationError,
    ChunkIndexingError,
    DocumentSoftDeleteError,
    SearchAccessDeniedError,
    TextSearchUnavailableError,
    TextStoreUnavailableError,
)
from app.rag.contracts import TextChunkStore
from app.rag.models import Chunk, DocumentSummary, SearchHit, TextQuery

INDEX_BATCH_SIZE = 1000
# Margen respecto a los 16 MB de Azure para serialización y envoltorio del SDK.
INDEX_BATCH_BYTES = 15_000_000
ACTIVE_DOCUMENT_FILTER = "deleted_at eq null"


class AzureTextSearchAdapter(TextChunkStore):
    def __init__(self, client: SearchClient) -> None:
        self._client = client

    def list_documents(self) -> list[DocumentSummary]:
        try:
            # Sin top: el iterador del SDK recorre todas las páginas del índice.
            results = self._client.search(
                search_text="*",
                filter=ACTIVE_DOCUMENT_FILTER,
                select=["document_id", "source"],
            )
            documents: dict[str, DocumentSummary] = {}
            for result in results:
                summary = DocumentSummary(
                    document_id=result["document_id"],
                    source=result["source"],
                    indexed_chunks=1,
                )
                if summary.document_id in documents:
                    documents[summary.document_id].indexed_chunks += 1
                else:
                    documents[summary.document_id] = summary
            return sorted(
                documents.values(),
                key=lambda document: (document.source.casefold(), document.document_id),
            )
        except AzureError as exc:
            if getattr(exc, "status_code", None) == 403:
                raise SearchAccessDeniedError() from exc
            raise TextSearchUnavailableError() from exc
        except (KeyError, TypeError, ValidationError) as exc:
            raise ApplicationError(
                "El índice de texto devolvió una lista de documentos incompatible.",
                status_code=502,
                code="invalid_document_list_response",
            ) from exc

    @staticmethod
    def _document(chunk: Chunk) -> dict[str, Any]:
        identity = json.dumps([chunk.document_id, chunk.id], ensure_ascii=False)
        return {
            "id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "content": chunk.content,
            "source": chunk.source,
            "page": chunk.page,
        }

    def index_chunks(self, chunks: Sequence[Chunk]) -> None:
        batch: list[dict[str, Any]] = []
        batch_bytes = 0
        for chunk in chunks:
            document = self._document(chunk)
            # ensure_ascii=True ofrece una cota conservadora para texto Unicode.
            size = len(json.dumps(document).encode("utf-8")) + 64
            if size > INDEX_BATCH_BYTES:
                raise ApplicationError(
                    "Un fragmento supera el tamaño máximo de indexación.",
                    status_code=413,
                    code="chunk_too_large",
                )
            if batch and (
                len(batch) >= INDEX_BATCH_SIZE or batch_bytes + size > INDEX_BATCH_BYTES
            ):
                self._merge_or_upload(batch)
                batch, batch_bytes = [], 0
            batch.append(document)
            batch_bytes += size
        if batch:
            self._merge_or_upload(batch)

    def _merge_or_upload(self, documents: list[dict[str, Any]]) -> None:
        try:
            # Conserva campos de ciclo de vida omitidos, como `deleted_at`, al
            # reindexar un chunk que ya existe.
            results = self._client.merge_or_upload_documents(documents=documents)
        except AzureError as exc:
            if getattr(exc, "status_code", None) == 403:
                raise SearchAccessDeniedError() from exc
            raise TextStoreUnavailableError() from exc
        succeeded = {result.key for result in results if result.succeeded}
        failed = [
            {"document_id": doc["document_id"], "chunk_id": doc["chunk_id"]}
            for doc in documents
            if doc["id"] not in succeeded
        ]
        if failed:
            raise ChunkIndexingError(failed)

    def soft_delete_document(
        self, document_id: str, *, deleted_at: datetime
    ) -> int | None:
        escaped_document_id = document_id.replace("'", "''")
        try:
            results = self._client.search(
                search_text="*",
                filter=f"document_id eq '{escaped_document_id}'",
                select=["id", "chunk_id", "deleted_at"],
            )
            documents: list[dict[str, str]] = []
            found_document = False
            for result in results:
                found_document = True
                key = result["id"]
                chunk_id = result["chunk_id"]
                if not isinstance(key, str) or not key:
                    raise TypeError
                if not isinstance(chunk_id, str) or not chunk_id:
                    raise TypeError
                if result.get("deleted_at") is None:
                    documents.append({"id": key, "chunk_id": chunk_id})
        except AzureError as exc:
            if getattr(exc, "status_code", None) == 403:
                raise SearchAccessDeniedError() from exc
            raise TextSearchUnavailableError() from exc
        except (KeyError, TypeError) as exc:
            raise ApplicationError(
                "El índice de texto devolvió datos incompatibles al eliminar.",
                status_code=502,
                code="invalid_document_delete_response",
            ) from exc

        # Distingue un documento inexistente de uno que ya estaba eliminado.
        if not documents:
            return 0 if found_document else None

        for offset in range(0, len(documents), INDEX_BATCH_SIZE):
            self._soft_delete_batch(
                document_id,
                documents[offset : offset + INDEX_BATCH_SIZE],
                deleted_at,
            )
        return len(documents)

    def _soft_delete_batch(
        self,
        document_id: str,
        documents: list[dict[str, str]],
        deleted_at: datetime,
    ) -> None:
        updates = [
            {"id": document["id"], "deleted_at": deleted_at} for document in documents
        ]
        try:
            results = self._client.merge_documents(documents=updates)
        except AzureError as exc:
            if getattr(exc, "status_code", None) == 403:
                raise SearchAccessDeniedError() from exc
            raise TextStoreUnavailableError() from exc
        succeeded = {result.key for result in results if result.succeeded}
        failed = [
            {"document_id": document_id, "chunk_id": document["chunk_id"]}
            for document in documents
            if document["id"] not in succeeded
        ]
        if failed:
            raise DocumentSoftDeleteError(failed)

    def search(self, query: TextQuery) -> list[SearchHit]:
        filters = [ACTIVE_DOCUMENT_FILTER]
        if query.document_id is not None:
            document_id = query.document_id.replace("'", "''")
            filters.append(f"document_id eq '{document_id}'")

        try:
            results = self._client.search(
                search_text=query.question,
                filter=" and ".join(filters),
                top=query.top_k,
                select=["chunk_id", "document_id", "content", "source", "page"],
            )
            return [
                SearchHit(
                    id=result["chunk_id"],
                    document_id=result["document_id"],
                    content=result["content"],
                    source=result["source"],
                    page=result.get("page"),
                    score=result["@search.score"],
                )
                for result in results
            ]
        except AzureError as exc:
            if getattr(exc, "status_code", None) == 403:
                raise SearchAccessDeniedError() from exc
            raise TextSearchUnavailableError() from exc
        except (KeyError, TypeError, ValidationError) as exc:
            raise ApplicationError(
                "El índice de texto devolvió una respuesta incompatible.",
                status_code=502,
                code="invalid_text_search_response",
            ) from exc
