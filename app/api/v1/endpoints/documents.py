from typing import Annotated

from fastapi import APIRouter, Depends, Path, UploadFile

from app.api.dependencies import (
    get_document_deletion_service,
    get_file_ingestion_service,
    get_ingestion_service,
    get_text_store,
)
from app.rag.contracts import TextChunkStore
from app.schemas.documents import (
    IndexChunksRequest,
    IndexChunksResponse,
    ListDocumentsResponse,
    SoftDeleteDocumentResponse,
    UploadDocumentResponse,
)
from app.services.document_deletion import DocumentDeletionService
from app.services.file_ingestion import FileIngestionService
from app.services.ingestion import IngestionService

router = APIRouter()


@router.get(
    "/documents",
    response_model=ListDocumentsResponse,
    summary="Listar documentos guardados en el índice de texto",
)
def list_documents(
    store: Annotated[TextChunkStore, Depends(get_text_store)],
) -> ListDocumentsResponse:
    return ListDocumentsResponse(documents=store.list_documents())


@router.delete(
    "/documents/{document_id}",
    response_model=SoftDeleteDocumentResponse,
    summary="Ocultar un documento y todos sus fragmentos",
)
def soft_delete_document(
    document_id: Annotated[str, Path(min_length=1, max_length=512)],
    service: Annotated[DocumentDeletionService, Depends(get_document_deletion_service)],
) -> SoftDeleteDocumentResponse:
    result = service.delete(document_id)
    return SoftDeleteDocumentResponse(
        document_id=result.document_id,
        soft_deleted_chunks=result.soft_deleted_chunks,
    )


@router.post(
    "/documents/upload",
    response_model=UploadDocumentResponse,
    summary="Extraer, dividir y guardar un archivo como fragmentos de texto",
)
def upload_document(
    file: UploadFile,
    service: Annotated[FileIngestionService, Depends(get_file_ingestion_service)],
) -> UploadDocumentResponse:
    try:
        result = service.ingest(file.filename, file.file)
    finally:
        file.file.close()
    return UploadDocumentResponse(
        document_id=result.document_id,
        source=result.source,
        indexed_chunks=result.indexed_chunks,
        warnings=result.warnings,
    )


@router.post(
    "/documents/chunks",
    response_model=IndexChunksResponse,
    summary="Indexar chunks con embeddings ya calculados",
)
def index_chunks(
    payload: IndexChunksRequest,
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> IndexChunksResponse:
    return IndexChunksResponse(indexed_chunks=service.index_chunks(payload.chunks))
