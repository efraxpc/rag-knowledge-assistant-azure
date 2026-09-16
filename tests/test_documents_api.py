from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.api.dependencies import get_text_store
from app.core.auth import require_user
from app.core.exceptions import (
    DocumentSoftDeleteError,
    SearchAccessDeniedError,
    TextSearchUnavailableError,
)
from app.rag.models import DocumentSummary
from tests.auth_helpers import authenticated_user, entra_settings


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(main, "get_settings", entra_settings)
    app = main.create_app()
    app.dependency_overrides[require_user] = authenticated_user
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "documents",
    [[], [DocumentSummary(document_id="doc-1", source="manual.pdf", indexed_chunks=4)]],
)
def test_lists_saved_documents(
    client: TestClient, documents: list[DocumentSummary]
) -> None:
    store = Mock()
    store.list_documents.return_value = documents
    client.app.dependency_overrides[get_text_store] = lambda: store

    response = client.get("/api/v1/documents")

    assert response.status_code == 200
    assert response.json() == {
        "documents": [document.model_dump() for document in documents]
    }
    store.list_documents.assert_called_once_with()


def test_listing_requires_login(client: TestClient) -> None:
    client.app.dependency_overrides.clear()
    assert client.get("/api/v1/documents").status_code == 401


def test_listing_requires_configured_text_store(client: TestClient) -> None:
    client.app.state.settings = entra_settings(
        azure_search_endpoint=None,
        azure_search_text_index_name=None,
        azure_search_index_name=None,
        azure_search_vector_dimensions=None,
    )
    response = client.get("/api/v1/documents")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "text_store_not_configured"


@pytest.mark.parametrize(
    "failure,status,code",
    [
        (SearchAccessDeniedError(), 403, "search_access_denied"),
        (TextSearchUnavailableError(), 503, "text_search_unavailable"),
    ],
)
def test_listing_reports_store_failure(
    client: TestClient, failure: Exception, status: int, code: str
) -> None:
    store = Mock()
    store.list_documents.side_effect = failure
    client.app.dependency_overrides[get_text_store] = lambda: store
    response = client.get("/api/v1/documents")
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize("deleted_chunks", [0, 4])
def test_soft_deletes_document_chunks(client: TestClient, deleted_chunks: int) -> None:
    store = Mock()
    store.soft_delete_document.return_value = deleted_chunks
    client.app.dependency_overrides[get_text_store] = lambda: store

    response = client.delete("/api/v1/documents/doc-1")

    assert response.status_code == 200
    assert response.json() == {
        "document_id": "doc-1",
        "soft_deleted_chunks": deleted_chunks,
    }
    deleted_at = store.soft_delete_document.call_args.kwargs["deleted_at"]
    assert deleted_at.utcoffset() is not None
    store.soft_delete_document.assert_called_once_with("doc-1", deleted_at=deleted_at)


def test_soft_delete_reports_unknown_document(client: TestClient) -> None:
    store = Mock()
    store.soft_delete_document.return_value = None
    client.app.dependency_overrides[get_text_store] = lambda: store

    response = client.delete("/api/v1/documents/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_soft_delete_requires_login(client: TestClient) -> None:
    client.app.dependency_overrides.clear()
    assert client.delete("/api/v1/documents/doc-1").status_code == 401


def test_soft_delete_reports_partial_failure(client: TestClient) -> None:
    store = Mock()
    store.soft_delete_document.side_effect = DocumentSoftDeleteError(
        [{"document_id": "doc-1", "chunk_id": "chunk-2"}]
    )
    client.app.dependency_overrides[get_text_store] = lambda: store

    response = client.delete("/api/v1/documents/doc-1")

    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "document_soft_delete_failed",
        "message": (
            "No se pudieron ocultar todos los chunks del documento. "
            "Puedes reintentar la eliminación."
        ),
        "details": {"failed_chunks": [{"document_id": "doc-1", "chunk_id": "chunk-2"}]},
    }
