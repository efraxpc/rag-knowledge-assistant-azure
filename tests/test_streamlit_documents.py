from collections.abc import Iterator
from unittest.mock import Mock

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from app import streamlit_app
from app.rag.models import DocumentSummary
from app.schemas.documents import SoftDeleteDocumentResponse
from app.schemas.queries import RagAnswerResponse


@pytest.fixture(autouse=True)
def clear_document_cache() -> Iterator[None]:
    fetch = streamlit_app.fetch_documents
    fetch.clear()
    yield
    fetch.clear()


def documents() -> list[DocumentSummary]:
    return [
        DocumentSummary(document_id="doc-1", source="manual.pdf", indexed_chunks=4),
        DocumentSummary(document_id="doc-2", source="guia.txt", indexed_chunks=2),
    ]


def test_fetches_documents_with_user_token_and_caches_per_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get = Mock(
        return_value=httpx.Response(
            200, json={"documents": [doc.model_dump() for doc in documents()]}
        )
    )
    monkeypatch.setattr(streamlit_app.httpx, "get", get)

    assert streamlit_app.fetch_documents(" http://api/ ", "user-token") == documents()
    assert streamlit_app.fetch_documents(" http://api/ ", "user-token") == documents()
    assert get.call_count == 1
    assert get.call_args.args == ("http://api/api/v1/documents",)
    assert get.call_args.kwargs["headers"] == {"Authorization": "Bearer user-token"}
    assert get.call_args.kwargs["follow_redirects"] is False

    streamlit_app.fetch_documents(" http://api/ ", "other-token")
    assert get.call_count == 2
    streamlit_app.fetch_documents.clear(" http://api/ ", "user-token")
    streamlit_app.fetch_documents(" http://api/ ", "user-token")
    assert get.call_count == 3


def test_listing_without_token_does_not_call_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get = Mock()
    monkeypatch.setattr(streamlit_app.httpx, "get", get)
    with pytest.raises(streamlit_app.DocumentListSessionExpiredError):
        streamlit_app.fetch_documents("http://api", "")
    get.assert_not_called()


def test_listing_401_requires_new_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        streamlit_app.httpx, "get", Mock(return_value=httpx.Response(401))
    )
    with pytest.raises(streamlit_app.DocumentListSessionExpiredError):
        streamlit_app.fetch_documents("http://api", "expired")


@pytest.mark.parametrize(
    "response,message",
    [
        (
            httpx.Response(403, json={"error": {"message": "Sin permisos"}}),
            "Sin permisos",
        ),
        (httpx.Response(503, text="Unavailable"), "respuesta no válida"),
        (httpx.Response(200, json={}), "respuesta no válida"),
        (
            httpx.Response(200, json={"documents": [{"source": "a.txt"}]}),
            "respuesta no válida",
        ),
        (httpx.Response(422, json={"detail": []}), "listar documentos"),
    ],
)
def test_listing_handles_invalid_api_responses(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response, message: str
) -> None:
    monkeypatch.setattr(streamlit_app.httpx, "get", Mock(return_value=response))
    with pytest.raises(streamlit_app.DocumentListError, match=message):
        streamlit_app.fetch_documents("http://api", "user-token")


def test_listing_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        streamlit_app.httpx,
        "get",
        Mock(side_effect=httpx.ReadTimeout("private detail")),
    )
    with pytest.raises(streamlit_app.DocumentListError, match="Actualizar documentos"):
        streamlit_app.fetch_documents("http://api", "user-token")


def test_soft_delete_sends_user_token(monkeypatch: pytest.MonkeyPatch) -> None:
    delete = Mock(
        return_value=httpx.Response(
            200,
            json={"document_id": "doc-1", "soft_deleted_chunks": 4},
        )
    )
    monkeypatch.setattr(streamlit_app.httpx, "delete", delete)

    result = streamlit_app.soft_delete_document(
        " http://api/ ", "doc-1", access_token="user-token"
    )

    assert result == SoftDeleteDocumentResponse(
        document_id="doc-1", soft_deleted_chunks=4
    )
    assert delete.call_args.args == ("http://api/api/v1/documents/doc-1",)
    assert delete.call_args.kwargs["headers"] == {"Authorization": "Bearer user-token"}
    assert delete.call_args.kwargs["follow_redirects"] is False


def test_soft_delete_requires_a_current_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delete = Mock()
    monkeypatch.setattr(streamlit_app.httpx, "delete", delete)
    with pytest.raises(streamlit_app.DocumentDeleteSessionExpiredError):
        streamlit_app.soft_delete_document("http://api", "doc-1", access_token="")
    delete.assert_not_called()


@pytest.mark.parametrize(
    "response,message",
    [
        (
            httpx.Response(403, json={"error": {"message": "Sin permisos"}}),
            "Sin permisos",
        ),
        (httpx.Response(503, text="Unavailable"), "respuesta no válida"),
        (httpx.Response(200, json={}), "respuesta no válida"),
        (httpx.Response(422, json={"detail": []}), "rechazó"),
    ],
)
def test_soft_delete_handles_invalid_api_responses(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response, message: str
) -> None:
    monkeypatch.setattr(streamlit_app.httpx, "delete", Mock(return_value=response))
    with pytest.raises(streamlit_app.DocumentDeleteError, match=message):
        streamlit_app.soft_delete_document(
            "http://api", "doc-1", access_token="user-token"
        )


def app(monkeypatch: pytest.MonkeyPatch, fetch: Mock) -> AppTest:
    monkeypatch.setattr(streamlit_app, "require_login", lambda: "user-token")
    monkeypatch.setattr(
        streamlit_app, "fetch_api_health", lambda _: {"version": "0.1.0"}
    )
    monkeypatch.setattr(streamlit_app, "fetch_documents", fetch)
    return AppTest.from_string("from app.streamlit_app import render_app\nrender_app()")


def test_saved_documents_show_in_new_session_and_can_be_queried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    at = app(monkeypatch, Mock(return_value=documents())).run()
    assert not at.exception
    assert at.dataframe[0].value.to_dict("records") == [
        {"Documento": "manual.pdf", "Fragmentos": 4},
        {"Documento": "guia.txt", "Fragmentos": 2},
    ]
    assert not at.chat_input[0].disabled
    assert at.selectbox(key="document_selection").value == "doc-1"
    assert at.chat_message[0].name == "assistant"
    assert len(at.pills) == 1

    ask = Mock(
        return_value=RagAnswerResponse(
            answer="Respuesta del manual",
            context=[
                {
                    "id": "chunk-1",
                    "document_id": "doc-1",
                    "content": "Fragmento usado para responder.",
                    "source": "manual.pdf",
                    "page": 2,
                    "score": 0.9,
                }
            ],
        )
    )
    monkeypatch.setattr(streamlit_app, "ask_question", ask)
    at.chat_input[0].set_value("¿Cómo usar el equipo?").run()
    assert not at.exception
    assert ask.call_args.kwargs["document_id"] == "doc-1"
    assert at.session_state["last_answer"]["answer"] == "Respuesta del manual"
    assert [message.name for message in at.chat_message] == [
        "user",
        "assistant",
    ]
    assert any(status.label == "Fuentes consultadas · 1" for status in at.status)
    assert any(
        caption.value == "Fragmento usado para responder." for caption in at.caption
    )

    at.selectbox(key="document_selection").set_value("doc-2").run()
    assert not at.exception
    assert "last_answer" not in at.session_state
    assert "chat_messages" not in at.session_state
    at.chat_input[0].set_value("¿Qué indica esta guía?").run()
    assert not at.exception
    assert ask.call_args.kwargs["document_id"] == "doc-2"


def test_question_error_remains_visible_in_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    at = app(monkeypatch, Mock(return_value=documents())).run()
    monkeypatch.setattr(
        streamlit_app,
        "ask_question",
        Mock(side_effect=streamlit_app.QuestionError("Azure no respondió")),
    )

    at.chat_input[0].set_value("¿Cómo uso el equipo?").run()

    assert not at.exception
    assert [message["role"] for message in at.session_state["chat_messages"]] == [
        "user",
        "assistant",
    ]
    assert at.session_state["chat_messages"][-1]["is_error"] is True
    assert at.session_state["last_error"] == "Azure no respondió"
    assert any(error.value == "Azure no respondió" for error in at.error)


def test_refresh_updates_documents_and_removes_stale_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch = Mock(side_effect=[[documents()[0]], [documents()[1]]])
    at = app(monkeypatch, fetch).run()
    at.button(key="refresh_documents").click().run()
    assert not at.exception
    fetch.clear.assert_called_once()
    assert at.selectbox(key="document_selection").value == "doc-2"
    assert at.dataframe[0].value["Documento"].tolist() == ["guia.txt"]


def test_empty_document_list_disables_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    at = app(monkeypatch, Mock(return_value=[])).run()
    assert not at.exception
    assert any("Todavía no hay documentos guardados" in info.value for info in at.info)
    assert not at.dataframe
    assert at.chat_input[0].disabled
    assert not at.pills


def test_document_error_is_visible_and_disables_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    at = app(
        monkeypatch, Mock(side_effect=streamlit_app.DocumentListError("Sin permisos"))
    ).run()
    assert not at.exception
    assert at.error[0].value == "Sin permisos"
    assert at.chat_input[0].disabled


def test_expired_session_offers_renewal(monkeypatch: pytest.MonkeyPatch) -> None:
    at = app(
        monkeypatch, Mock(side_effect=streamlit_app.DocumentListSessionExpiredError())
    ).run()
    assert not at.exception
    assert at.session_state["session_expired"] is True
    assert at.button(key="renew_session").label == "Renovar sesión"
    assert not at.chat_input
    at.run()
    assert not at.exception
    assert at.button(key="renew_session").label == "Renovar sesión"


def test_new_upload_is_visible_before_search_refreshes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(streamlit_app, "fetch_documents", Mock(return_value=[]))
    at = AppTest.from_string(
        "from app.streamlit_app import render_documents\n"
        "render_documents('http://api', 'user-token')"
    )
    at.session_state["upload_result"] = {**documents()[0].model_dump(), "warnings": []}
    at.session_state["document_selection"] = "doc-1"
    at.run()
    assert not at.exception
    assert at.dataframe[0].value["Documento"].tolist() == ["manual.pdf"]
    assert at.selectbox(key="document_selection").value == "doc-1"


def test_deleting_selected_document_requires_confirmation_and_clears_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch = Mock(return_value=documents())
    delete = Mock(
        return_value=SoftDeleteDocumentResponse(
            document_id="doc-1", soft_deleted_chunks=4
        )
    )
    monkeypatch.setattr(streamlit_app, "soft_delete_document", delete)
    at = app(monkeypatch, fetch).run()
    at.session_state["chat_messages"] = [
        {"role": "assistant", "content": "Respuesta anterior"}
    ]
    at.session_state["last_answer"] = {"answer": "Respuesta anterior"}

    at.button(key="delete_document").click().run()

    assert not at.exception
    delete.assert_not_called()
    assert at.button(key="confirm_document_delete").label == "Eliminar"
    assert any("todos los usuarios" in warning.value for warning in at.warning)

    at.button(key="confirm_document_delete").click().run()

    assert not at.exception
    delete.assert_called_once_with(
        "http://localhost:8000", "doc-1", access_token="user-token"
    )
    assert at.session_state["soft_deleted_document_ids"] == ["doc-1"]
    assert "chat_messages" not in at.session_state
    assert "last_answer" not in at.session_state
    assert at.selectbox(key="document_selection").value == "doc-2"
    assert at.dataframe[0].value["Documento"].tolist() == ["guia.txt"]


def test_canceling_delete_keeps_document(monkeypatch: pytest.MonkeyPatch) -> None:
    delete = Mock()
    monkeypatch.setattr(streamlit_app, "soft_delete_document", delete)
    at = app(monkeypatch, Mock(return_value=documents())).run()

    at.button(key="delete_document").click().run()
    at.button(key="cancel_document_delete").click().run()

    assert not at.exception
    delete.assert_not_called()
    assert at.selectbox(key="document_selection").value == "doc-1"
    assert at.dataframe[0].value["Documento"].tolist() == [
        "manual.pdf",
        "guia.txt",
    ]


def test_failed_delete_keeps_document_and_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        streamlit_app,
        "soft_delete_document",
        Mock(side_effect=streamlit_app.DocumentDeleteError("Azure no respondió")),
    )
    at = app(monkeypatch, Mock(return_value=documents())).run()
    messages = [{"role": "assistant", "content": "Respuesta anterior"}]
    at.session_state["chat_messages"] = messages

    at.button(key="delete_document").click().run()
    at.button(key="confirm_document_delete").click().run()

    assert not at.exception
    assert any(error.value == "Azure no respondió" for error in at.error)
    assert at.session_state["chat_messages"] == messages
    assert "soft_deleted_document_ids" not in at.session_state
    assert at.dataframe[0].value["Documento"].tolist() == [
        "manual.pdf",
        "guia.txt",
    ]
