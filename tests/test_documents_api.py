from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.api.dependencies import get_text_store
from app.core.auth import require_user
from app.core.exceptions import SearchAccessDeniedError, TextSearchUnavailableError
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
