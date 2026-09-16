from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends, Request

from app.core.auth import AuthenticatedUser, require_user
from app.core.exceptions import ApplicationError
from app.core.resources import (
    open_text_store,
    open_user_chat_client,
    open_vector_store,
)
from app.rag.contracts import TextChunkStore, TextCompletionClient, VectorStore
from app.services.answer import AnswerService
from app.services.answer_graph import AnswerGraphOptions
from app.services.document_deletion import DocumentDeletionService
from app.services.file_ingestion import FileIngestionService
from app.services.ingestion import IngestionService
from app.services.query import QueryService


def get_text_store(
    request: Request, user: Annotated[AuthenticatedUser, Depends(require_user)]
) -> Iterator[TextChunkStore]:
    with open_text_store(
        request.app.state.settings, user_assertion=user.assertion
    ) as store:
        if store is None:
            raise ApplicationError(
                "Configura el endpoint y el índice de texto de Azure AI Search.",
                status_code=503,
                code="text_store_not_configured",
            )
        yield store


def get_file_ingestion_service(
    store: Annotated[TextChunkStore, Depends(get_text_store)],
) -> FileIngestionService:
    return FileIngestionService(store)


def get_document_deletion_service(
    store: Annotated[TextChunkStore, Depends(get_text_store)],
) -> DocumentDeletionService:
    return DocumentDeletionService(store)


def get_text_completion_client(
    request: Request, user: Annotated[AuthenticatedUser, Depends(require_user)]
) -> Iterator[TextCompletionClient]:
    with open_user_chat_client(
        request.app.state.settings, user_assertion=user.assertion
    ) as client:
        if client is None:
            raise ApplicationError(
                "Configura el endpoint y el despliegue generador de Azure OpenAI.",
                status_code=503,
                code="rag_generator_not_configured",
            )
        yield client


def get_answer_service(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(require_user)],
    store: Annotated[TextChunkStore, Depends(get_text_store)],
) -> AnswerService:
    settings = request.app.state.settings

    @contextmanager
    def completion_client_factory() -> Iterator[TextCompletionClient]:
        with open_user_chat_client(settings, user_assertion=user.assertion) as client:
            if client is None:
                raise ApplicationError(
                    "Configura el endpoint y el despliegue generador de Azure OpenAI.",
                    status_code=503,
                    code="rag_generator_not_configured",
                )
            yield client

    options = AnswerGraphOptions(
        max_search_attempts=settings.rag_max_search_attempts,
        max_generation_attempts=settings.rag_max_generation_attempts,
        max_context_characters=settings.rag_max_context_characters,
        verify_citations=settings.rag_verify_citations,
        trace_enabled=settings.rag_trace_enabled,
    )
    return AnswerService(
        store, completion_client_factory=completion_client_factory, options=options
    )


def get_vector_store(
    request: Request, user: Annotated[AuthenticatedUser, Depends(require_user)]
) -> Iterator[VectorStore]:
    with open_vector_store(
        request.app.state.settings, user_assertion=user.assertion
    ) as store:
        if store is None:
            raise ApplicationError(
                "Configura el endpoint, el índice y las dimensiones de "
                "Azure AI Search.",
                status_code=503,
                code="vector_store_not_configured",
            )
        yield store


def get_ingestion_service(
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
) -> IngestionService:
    return IngestionService(vector_store)


def get_query_service(
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
) -> QueryService:
    return QueryService(vector_store)
