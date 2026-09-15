from unittest.mock import Mock

import pytest
from azure.core.exceptions import HttpResponseError, ServiceRequestError
from azure.search.documents import SearchClient
from azure.search.documents.models import IndexingResult

from app.core.exceptions import (
    ApplicationError,
    ChunkIndexingError,
    SearchAccessDeniedError,
    TextSearchUnavailableError,
    TextStoreUnavailableError,
)
from app.integrations import azure_text_search
from app.integrations.azure_text_search import AzureTextSearchAdapter
from app.rag.models import Chunk, DocumentSummary, TextQuery


@pytest.fixture
def client() -> Mock:
    client = Mock(spec=SearchClient)
    client.upload_documents.side_effect = lambda documents: [
        IndexingResult.deserialize({"key": doc["id"], "status": True})
        for doc in documents
    ]
    return client


def chunk(number: int = 0, content: str = "Texto") -> Chunk:
    return Chunk(
        id=str(number), document_id="doc", content=content, source="manual.pdf", page=1
    )


def test_lists_documents_and_counts_all_chunks(client: Mock) -> None:
    # Más de una página de resultados, con nombres iguales e IDs distintos.
    client.search.return_value = iter(
        [
            {"document_id": "doc-2", "source": "manual.pdf"},
            *[{"document_id": "doc-1", "source": "manual.pdf"} for _ in range(1001)],
            {"document_id": "doc-3", "source": "A.txt"},
            {"document_id": "doc-2", "source": "manual.pdf"},
        ]
    )
    assert AzureTextSearchAdapter(client).list_documents() == [
        DocumentSummary(document_id="doc-3", source="A.txt", indexed_chunks=1),
        DocumentSummary(document_id="doc-1", source="manual.pdf", indexed_chunks=1001),
        DocumentSummary(document_id="doc-2", source="manual.pdf", indexed_chunks=2),
    ]
    client.search.assert_called_once_with(
        search_text="*", select=["document_id", "source"]
    )


def test_lists_empty_index(client: Mock) -> None:
    client.search.return_value = []
    assert AzureTextSearchAdapter(client).list_documents() == []


@pytest.mark.parametrize("result", [{}, {"document_id": "doc", "source": ""}, None])
def test_rejects_incompatible_document_list(client: Mock, result: object) -> None:
    client.search.return_value = [result]
    with pytest.raises(ApplicationError) as error:
        AzureTextSearchAdapter(client).list_documents()
    assert error.value.status_code == 502
    assert error.value.code == "invalid_document_list_response"


@pytest.mark.parametrize(
    "status,error_type",
    [(403, SearchAccessDeniedError), (503, TextSearchUnavailableError)],
)
def test_listing_handles_failure_during_iteration(
    client: Mock, status: int, error_type: type[ApplicationError]
) -> None:
    def results():
        yield {"document_id": "doc", "source": "manual.pdf"}
        error = HttpResponseError("private detail")
        error.status_code = status
        raise error

    client.search.return_value = results()
    with pytest.raises(error_type) as error:
        AzureTextSearchAdapter(client).list_documents()
    assert "private detail" not in str(error.value)


def test_maps_text_and_reuses_keys(client: Mock) -> None:
    adapter = AzureTextSearchAdapter(client)
    adapter.index_chunks([chunk()])
    first = client.upload_documents.call_args.kwargs["documents"][0]
    adapter.index_chunks([chunk(content="Actualizado")])
    second = client.upload_documents.call_args.kwargs["documents"][0]
    assert len(first["id"]) == 64
    assert first["id"] == second["id"]
    assert first == {
        "id": first["id"],
        "chunk_id": "0",
        "document_id": "doc",
        "content": "Texto",
        "source": "manual.pdf",
        "page": 1,
    }
    assert second["content"] == "Actualizado"


def test_splits_by_document_count(client: Mock) -> None:
    AzureTextSearchAdapter(client).index_chunks([chunk(i) for i in range(1001)])
    assert [
        len(c.kwargs["documents"]) for c in client.upload_documents.call_args_list
    ] == [1000, 1]


def test_splits_by_serialized_bytes(
    client: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(azure_text_search, "INDEX_BATCH_BYTES", 14_000)
    AzureTextSearchAdapter(client).index_chunks(
        [chunk(i, "á" * 1000) for i in range(3)]
    )
    assert [
        len(c.kwargs["documents"]) for c in client.upload_documents.call_args_list
    ] == [2, 1]


@pytest.mark.parametrize("missing_result", [True, False])
def test_reports_failed_or_missing_results(client: Mock, missing_result: bool) -> None:
    def upload(documents: list[dict]) -> list[IndexingResult]:
        return [
            IndexingResult.deserialize({"key": doc["id"], "status": index == 0})
            for index, doc in enumerate(documents)
            if index == 0 or not missing_result
        ]

    client.upload_documents.side_effect = upload
    with pytest.raises(ChunkIndexingError) as error:
        AzureTextSearchAdapter(client).index_chunks([chunk(0), chunk(1)])
    assert error.value.details == {
        "failed_chunks": [{"document_id": "doc", "chunk_id": "1"}]
    }


def test_provider_failure_has_no_private_details(client: Mock) -> None:
    client.upload_documents.side_effect = HttpResponseError("private detail")
    with pytest.raises(TextStoreUnavailableError) as error:
        AzureTextSearchAdapter(client).index_chunks([chunk()])
    assert "private detail" not in str(error.value)


def test_stops_after_failed_batch(
    client: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(azure_text_search, "INDEX_BATCH_SIZE", 1)
    client.upload_documents.side_effect = HttpResponseError()
    with pytest.raises(TextStoreUnavailableError):
        AzureTextSearchAdapter(client).index_chunks([chunk(0), chunk(1)])
    assert client.upload_documents.call_count == 1


def test_searches_text_with_filter_and_maps_context(client: Mock) -> None:
    client.search.return_value = [
        {
            "chunk_id": "chunk-1",
            "document_id": "O'Brien",
            "content": "Desconecta el equipo.",
            "source": "manual.pdf",
            "page": 2,
            "@search.score": 0.8,
        }
    ]

    results = AzureTextSearchAdapter(client).search(
        TextQuery(question="¿Qué debo hacer?", document_id="O'Brien", top_k=3)
    )

    arguments = client.search.call_args.kwargs
    assert arguments["search_text"] == "¿Qué debo hacer?"
    assert arguments["filter"] == "document_id eq 'O''Brien'"
    assert arguments["top"] == 3
    assert results[0].source == "manual.pdf"
    assert results[0].page == 2
    assert results[0].score == 0.8


def test_search_failure_is_controlled(client: Mock) -> None:
    def results() -> object:
        raise ServiceRequestError("private detail")
        yield  # pragma: no cover

    client.search.return_value = results()
    with pytest.raises(TextSearchUnavailableError) as error:
        AzureTextSearchAdapter(client).search(TextQuery(question="pregunta"))
    assert "private detail" not in str(error.value)
