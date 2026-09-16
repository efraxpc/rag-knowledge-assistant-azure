"""Interfaz conversacional para consultar manuales con RAG."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import httpx
import streamlit as st
from pydantic import ValidationError

from app.core.config import get_settings
from app.rag.models import DocumentSummary
from app.schemas.documents import (
    ListDocumentsResponse,
    SoftDeleteDocumentResponse,
    UploadDocumentResponse,
)
from app.schemas.queries import RagAnswerResponse
from app.services.file_ingestion import MAX_UPLOAD_BYTES
from app.ui_auth import require_login

SUPPORTED_FILE_TYPES = ["pdf", "txt", "md"]
SUGGESTED_QUESTIONS = (
    "Resume los puntos principales del manual",
    "¿Qué pasos debo seguir para ponerlo en marcha?",
    "¿Qué precauciones de seguridad debo tener en cuenta?",
)


class ApiUnavailableError(RuntimeError):
    """Indica que la interfaz no pudo consultar el estado de la API."""


class DocumentUploadError(RuntimeError):
    """Error de carga que se puede mostrar en la interfaz."""


class SessionExpiredError(DocumentUploadError):
    """La API solicita renovar el inicio de sesión."""


class QuestionError(RuntimeError):
    """Error de consulta que se puede mostrar en la interfaz."""


class QuestionSessionExpiredError(QuestionError):
    """La consulta requiere renovar el inicio de sesión."""


class DocumentListError(RuntimeError):
    """Error al recuperar los documentos guardados."""


class DocumentListSessionExpiredError(DocumentListError):
    """La lista de documentos requiere renovar el inicio de sesión."""


class DocumentDeleteError(RuntimeError):
    """Error de borrado suave que se puede mostrar en la interfaz."""


class DocumentDeleteSessionExpiredError(DocumentDeleteError):
    """El borrado requiere renovar el inicio de sesión."""


@st.cache_data(ttl=30, max_entries=128, show_spinner=False)
def fetch_documents(api_url: str, access_token: str) -> list[DocumentSummary]:
    """Consulta el índice con la identidad del usuario y una caché breve."""
    if not access_token:
        raise DocumentListSessionExpiredError(
            "Inicia sesión con Microsoft para ver los documentos."
        )
    url = f"{api_url.strip().rstrip('/')}/api/v1/documents"
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=httpx.Timeout(30, connect=5),
            follow_redirects=False,
        )
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        raise DocumentListError(
            "No se pudieron cargar los documentos. Pulsa Actualizar documentos."
        ) from exc
    if response.status_code == 401:
        raise DocumentListSessionExpiredError(
            "Tu sesión caducó. Vuelve a iniciar sesión."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise DocumentListError("La API devolvió una respuesta no válida.") from exc
    if response.is_error:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error.get("message") if isinstance(error, dict) else None
        raise DocumentListError(
            message if isinstance(message, str) else "No se pudieron listar documentos."
        )
    try:
        return ListDocumentsResponse.model_validate(payload).documents
    except ValidationError as exc:
        raise DocumentListError("La API devolvió una respuesta no válida.") from exc


def upload_document(
    api_url: str, filename: str, data: bytes, *, access_token: str
) -> UploadDocumentResponse:
    if not access_token:
        raise SessionExpiredError("Inicia sesión con Microsoft para cargar archivos.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentUploadError("El archivo supera el límite de 10 MiB.")
    url = f"{api_url.strip().rstrip('/')}/api/v1/documents/upload"
    try:
        response = httpx.post(
            url,
            files={"file": (filename, data, "application/octet-stream")},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=httpx.Timeout(120, connect=5),
            follow_redirects=False,
        )
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        raise DocumentUploadError(
            "No se pudo completar la carga. Puedes reintentar con el mismo archivo."
        ) from exc
    if response.status_code == 401:
        raise SessionExpiredError("Tu sesión caducó. Vuelve a iniciar sesión.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise DocumentUploadError("La API devolvió una respuesta no válida.") from exc
    if response.is_error:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error.get("message") if isinstance(error, dict) else None
        raise DocumentUploadError(
            message if isinstance(message, str) else "La API rechazó el archivo."
        )
    try:
        return UploadDocumentResponse.model_validate(payload)
    except ValidationError as exc:
        raise DocumentUploadError("La API devolvió una respuesta no válida.") from exc


def soft_delete_document(
    api_url: str, document_id: str, *, access_token: str
) -> SoftDeleteDocumentResponse:
    if not access_token:
        raise DocumentDeleteSessionExpiredError(
            "Inicia sesión con Microsoft para eliminar documentos."
        )
    url = f"{api_url.strip().rstrip('/')}/api/v1/documents/{document_id}"
    try:
        response = httpx.delete(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=httpx.Timeout(120, connect=5),
            follow_redirects=False,
        )
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        raise DocumentDeleteError(
            "No se pudo eliminar el documento. Puedes reintentar."
        ) from exc
    if response.status_code == 401:
        raise DocumentDeleteSessionExpiredError(
            "Tu sesión caducó. Vuelve a iniciar sesión."
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise DocumentDeleteError("La API devolvió una respuesta no válida.") from exc
    if response.is_error:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error.get("message") if isinstance(error, dict) else None
        raise DocumentDeleteError(
            message if isinstance(message, str) else "La API rechazó la eliminación."
        )
    try:
        return SoftDeleteDocumentResponse.model_validate(payload)
    except ValidationError as exc:
        raise DocumentDeleteError("La API devolvió una respuesta no válida.") from exc


def ask_question(
    api_url: str,
    question: str,
    *,
    access_token: str,
    document_id: str,
) -> RagAnswerResponse:
    if not access_token:
        raise QuestionSessionExpiredError(
            "Inicia sesión con Microsoft para consultar manuales."
        )
    url = f"{api_url.strip().rstrip('/')}/api/v1/queries/answer"
    try:
        response = httpx.post(
            url,
            json={"question": question, "document_id": document_id, "top_k": 5},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=httpx.Timeout(90, connect=5),
            follow_redirects=False,
        )
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        raise QuestionError("No se pudo completar la consulta.") from exc
    if response.status_code == 401:
        raise QuestionSessionExpiredError("Tu sesión caducó. Vuelve a iniciar sesión.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise QuestionError("La API devolvió una respuesta no válida.") from exc
    if response.is_error:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error.get("message") if isinstance(error, dict) else None
        raise QuestionError(
            message if isinstance(message, str) else "La API rechazó la consulta."
        )
    try:
        return RagAnswerResponse.model_validate(payload)
    except ValidationError as exc:
        raise QuestionError("La API devolvió una respuesta no válida.") from exc


def build_health_url(api_url: str) -> str:
    """Construye la URL del health check sin duplicar separadores."""
    return f"{api_url.strip().rstrip('/')}/api/v1/health"


@st.cache_data(ttl=30, show_spinner=False)
def fetch_api_health(api_url: str) -> dict[str, Any]:
    """Obtiene el estado de la API configurada."""
    try:
        request = Request(
            build_health_url(api_url),
            headers={"Accept": "application/json"},
        )
        with urlopen(request, timeout=2) as response:  # noqa: S310
            payload = json.load(response)
    except (
        HTTPError,
        URLError,
        TimeoutError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise ApiUnavailableError("No se pudo conectar con la API.") from exc

    if not isinstance(payload, dict) or payload.get("status") != "ok":
        raise ApiUnavailableError("La API devolvió un estado no válido.")

    return payload


def render_sidebar() -> str:
    """Muestra el estado de la API y devuelve su URL configurada."""
    with st.sidebar:
        st.header("Espacio de trabajo", icon=":material/tune:")
        # El destino del token lo fija el despliegue, no un campo editable del usuario.
        api_url = get_settings().api_base_url

        if st.button(
            "Actualizar estado",
            icon=":material/refresh:",
            width="stretch",
        ):
            fetch_api_health.clear()

        try:
            health = fetch_api_health(api_url)
        except ApiUnavailableError:
            st.error("API no disponible")
        else:
            version = health.get("version", "desconocida")
            st.success(f"API conectada · v{version}")

    return api_url


def render_session_expired() -> bool:
    """Permite renovar una sesión caducada en cualquier sección de la pantalla."""
    if st.session_state.get("session_expired") is not True:
        return False
    st.warning("Tu sesión caducó. Vuelve a iniciar sesión para continuar.")
    if st.button("Renovar sesión", key="renew_session"):
        st.session_state.clear()
        st.logout()
    return True


def render_document_upload(manual: Any, api_url: str, access_token: str) -> None:
    """Solo envía archivos al pulsar el botón, nunca durante un rerun."""
    selection = (api_url.strip().rstrip("/"), manual.name, manual.file_id)
    if st.session_state.get("upload_selection") != selection:
        st.session_state["upload_selection"] = selection
        st.session_state.pop("upload_result", None)
        clear_conversation()
    if st.button(
        "Procesar y guardar",
        type="primary",
        icon=":material/upload_file:",
        width="stretch",
    ):
        st.session_state.pop("upload_result", None)
        with st.spinner("Procesando y guardando fragmentos…"):
            try:
                result = upload_document(
                    api_url, manual.name, manual.getvalue(), access_token=access_token
                )
            except SessionExpiredError:
                st.session_state["session_expired"] = True
            except DocumentUploadError as exc:
                st.error(str(exc))
            else:
                st.session_state["upload_result"] = result.model_dump()
                st.session_state["document_selection"] = result.document_id
                fetch_documents.clear(api_url, access_token)
    if render_session_expired():
        return
    result = st.session_state.get("upload_result")
    if result:
        st.success(f"Se guardaron {result['indexed_chunks']} fragmentos del archivo.")
        for warning in result["warnings"]:
            st.warning(warning)


def dismiss_document_deletion() -> None:
    st.session_state.pop("pending_document_delete", None)


@st.dialog(
    "Eliminar manual",
    icon=":material/delete:",
    on_dismiss=dismiss_document_deletion,
)
def confirm_document_deletion(
    document: DocumentSummary, api_url: str, access_token: str
) -> None:
    st.warning(
        f"Se ocultará **{document.source}** y sus "
        f"**{document.indexed_chunks} fragmentos** para todos los usuarios. "
        "Ya no se usarán para responder preguntas."
    )
    st.caption(
        "Los datos se conservarán en Azure AI Search, pero no podrán restaurarse "
        "desde esta aplicación."
    )
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Cancelar", key="cancel_document_delete"):
            dismiss_document_deletion()
            st.rerun()
        delete_confirmed = st.button(
            "Eliminar",
            key="confirm_document_delete",
            type="primary",
            icon=":material/delete:",
        )
    if not delete_confirmed:
        return

    with st.spinner("Ocultando el manual y sus fragmentos…"):
        try:
            soft_delete_document(
                api_url,
                document.document_id,
                access_token=access_token,
            )
        except DocumentDeleteSessionExpiredError:
            dismiss_document_deletion()
            st.session_state["session_expired"] = True
            st.rerun()
        except DocumentDeleteError as exc:
            st.error(str(exc))
            return

    hidden_ids = {
        value
        for value in st.session_state.get("soft_deleted_document_ids", [])
        if isinstance(value, str)
    }
    hidden_ids.add(document.document_id)
    st.session_state["soft_deleted_document_ids"] = sorted(hidden_ids)
    dismiss_document_deletion()
    upload_result = st.session_state.get("upload_result")
    if (
        isinstance(upload_result, dict)
        and upload_result.get("document_id") == document.document_id
    ):
        st.session_state.pop("upload_result", None)
    st.session_state["document_delete_success"] = document.source
    fetch_documents.clear(api_url, access_token)
    clear_conversation()
    st.rerun()


def render_documents(api_url: str, access_token: str) -> str | None:
    """Muestra documentos persistidos y devuelve el seleccionado para consultar."""
    st.subheader("Tus manuales", icon=":material/library_books:")
    deleted_source = st.session_state.pop("document_delete_success", None)
    if isinstance(deleted_source, str):
        st.toast(f"{deleted_source} se eliminó de la biblioteca.")
    if st.button(
        "Actualizar documentos",
        key="refresh_documents",
        icon=":material/sync:",
        width="stretch",
    ):
        fetch_documents.clear(api_url, access_token)
    try:
        documents = fetch_documents(api_url, access_token)
    except DocumentListSessionExpiredError:
        st.session_state["session_expired"] = True
        render_session_expired()
        return None
    except DocumentListError as exc:
        st.error(str(exc))
        return None

    hidden_ids = {
        value
        for value in st.session_state.get("soft_deleted_document_ids", [])
        if isinstance(value, str)
    }
    documents = [
        document for document in documents if document.document_id not in hidden_ids
    ]

    # Search puede tardar en mostrar una carga recién confirmada por la API.
    upload_result = st.session_state.get("upload_result")
    if (
        upload_result
        and upload_result["document_id"] not in hidden_ids
        and all(
            document.document_id != upload_result["document_id"]
            for document in documents
        )
    ):
        documents.append(
            DocumentSummary(
                document_id=upload_result["document_id"],
                source=upload_result["source"],
                indexed_chunks=upload_result["indexed_chunks"],
            )
        )
    if not documents:
        st.info(
            "Todavía no hay documentos guardados. Sube uno para comenzar.",
            icon=":material/info:",
        )
        st.session_state.pop("document_selection", None)
        st.session_state.pop("answer_document_id", None)
        st.session_state.pop("selected_document_source", None)
        dismiss_document_deletion()
        clear_conversation()
        return None

    pending_delete = st.session_state.get("pending_document_delete")
    if isinstance(pending_delete, dict):
        try:
            pending_document = DocumentSummary.model_validate(pending_delete)
        except ValidationError:
            dismiss_document_deletion()
        else:
            if any(
                document.document_id == pending_document.document_id
                for document in documents
            ):
                confirm_document_deletion(
                    pending_document,
                    api_url,
                    access_token,
                )
            else:
                dismiss_document_deletion()

    with st.expander(
        f"Biblioteca · {len(documents)}",
        icon=":material/folder_open:",
    ):
        st.dataframe(
            [
                {
                    "Documento": document.source,
                    "Fragmentos": document.indexed_chunks,
                }
                for document in documents
            ],
            hide_index=True,
            width="stretch",
        )
    sources = {document.document_id: document.source for document in documents}
    names = Counter(document.source for document in documents)
    labels = {
        document_id: (f"{source} · {document_id[:8]}" if names[source] > 1 else source)
        for document_id, source in sources.items()
    }
    if st.session_state.get("document_selection") not in sources:
        st.session_state.pop("document_selection", None)
    document_id = st.selectbox(
        "Documento para consultar",
        options=list(sources),
        format_func=labels.__getitem__,
        key="document_selection",
    )
    selected_document = next(
        document for document in documents if document.document_id == document_id
    )
    if st.button(
        "Eliminar manual",
        key="delete_document",
        icon=":material/delete:",
        width="stretch",
    ):
        st.session_state["pending_document_delete"] = selected_document.model_dump()
        st.rerun()
    if st.session_state.get("answer_document_id") != document_id:
        st.session_state["answer_document_id"] = document_id
        clear_conversation()
    st.session_state["selected_document_source"] = sources[document_id]
    return document_id


def clear_conversation() -> None:
    """Elimina solo el historial asociado al manual activo."""
    for key in ("chat_messages", "last_question", "last_answer", "last_error"):
        st.session_state.pop(key, None)


def render_sources(context: list[dict[str, Any]]) -> None:
    """Presenta los fragmentos usados sin apartar la atención de la respuesta."""
    if not context:
        return

    label = f"Fuentes consultadas · {len(context)}"
    with st.expander(
        label,
        icon=":material/find_in_page:",
        type="compact",
    ):
        for index, hit in enumerate(context, start=1):
            source = str(hit.get("source", "Documento"))
            page = hit.get("page")
            location = f"{source} · página {page}" if page else source
            st.markdown(f"**{index}. {location}**")
            st.caption(str(hit.get("content", "")))


def render_chat_message(message: dict[str, Any]) -> None:
    """Dibuja un turno persistido y sus fuentes, si las tiene."""
    role = str(message.get("role", "assistant"))
    avatar = ":material/person:" if role == "user" else ":material/smart_toy:"
    with st.chat_message(role, avatar=avatar):
        content = str(message.get("content", ""))
        if message.get("is_error") is True:
            st.error(content, icon=":material/error:")
        else:
            st.markdown(content)
        context = message.get("context", [])
        if role == "assistant" and isinstance(context, list):
            render_sources(context)


def render_chat(
    api_url: str,
    access_token: str,
    document_id: str | None,
) -> None:
    """Muestra el historial y procesa nuevos turnos de conversación."""
    messages = st.session_state.get("chat_messages", [])
    if not isinstance(messages, list):
        messages = []
        st.session_state["chat_messages"] = messages

    for message in messages:
        if isinstance(message, dict):
            render_chat_message(message)

    suggested_question = None
    if not messages:
        source = st.session_state.get("selected_document_source")
        with st.chat_message("assistant", avatar=":material/smart_toy:"):
            if document_id is None:
                st.markdown(
                    "Selecciona un manual en la barra lateral o sube uno nuevo "
                    "para empezar a conversar."
                )
            else:
                st.markdown(
                    f"Estoy listo para ayudarte con **{source}**. Puedes hacerme "
                    "una pregunta concreta o empezar con una de estas ideas."
                )
        if document_id is not None:
            suggested_question = st.pills(
                "Preguntas sugeridas",
                SUGGESTED_QUESTIONS,
                label_visibility="collapsed",
                selection_mode="single",
            )

    placeholder = (
        "Pregunta sobre el manual…"
        if document_id is not None
        else "Selecciona un manual para empezar"
    )
    typed_question = st.chat_input(
        placeholder,
        key="chat_question",
        disabled=document_id is None,
        submit_mode="disable",
    )
    question = typed_question or suggested_question
    if not isinstance(question, str) or not question.strip() or document_id is None:
        return

    question = question.strip()
    user_message = {"role": "user", "content": question}
    messages.append(user_message)
    st.session_state["chat_messages"] = messages
    st.session_state["last_question"] = question
    st.session_state.pop("last_answer", None)
    render_chat_message(user_message)

    with st.chat_message("assistant", avatar=":material/smart_toy:"):
        with st.status(
            ":shimmer[Consultando el manual]",
            type="compact",
        ) as status:
            try:
                result = ask_question(
                    api_url,
                    question,
                    access_token=access_token,
                    document_id=document_id,
                )
            except QuestionSessionExpiredError:
                st.session_state["session_expired"] = True
                status.update(
                    label="La sesión caducó",
                    state="error",
                )
                render_session_expired()
                return
            except QuestionError as exc:
                status.update(
                    label="No se pudo completar la consulta",
                    state="error",
                )
                error = str(exc)
                messages.append(
                    {
                        "role": "assistant",
                        "content": error,
                        "is_error": True,
                    }
                )
                st.session_state["chat_messages"] = messages
                st.session_state["last_error"] = error
                st.rerun()
            status.update(label="Respuesta preparada", state="complete")

        answer = result.model_dump()
        st.markdown(answer["answer"])
        render_sources(answer["context"])

    messages.append(
        {
            "role": "assistant",
            "content": answer["answer"],
            "context": answer["context"],
        }
    )
    st.session_state["chat_messages"] = messages
    st.session_state["last_answer"] = answer
    st.session_state.pop("last_error", None)
    # Reconstruye la conversación desde el estado persistido. Así la respuesta no
    # depende de los elementos transitorios del rerun que ejecutó la petición.
    st.rerun()


def render_app() -> None:
    """Renderiza la aplicación Streamlit."""
    st.set_page_config(
        page_title="Asistente de manuales",
        page_icon=":material/smart_toy:",
        layout="centered",
    )

    access_token = require_login()
    if access_token is None:
        return

    if render_session_expired():
        return

    api_url = render_sidebar()
    with st.sidebar:
        st.subheader("Añadir un manual", icon=":material/upload_file:")
        manual = st.file_uploader(
            "Carga un archivo",
            type=SUPPORTED_FILE_TYPES,
            help="PDF con texto, TXT y Markdown. Máximo 10 MiB; sin OCR.",
        )
        if manual is None:
            st.session_state.pop("upload_selection", None)
            st.session_state.pop("upload_result", None)
        else:
            st.caption(f"{manual.name} · {manual.size / 1024:.1f} KB")
            render_document_upload(manual, api_url, access_token)

        if st.session_state.get("session_expired"):
            return
        document_id = render_documents(api_url, access_token)

        messages = st.session_state.get("chat_messages", [])
        if st.button(
            "Nueva conversación",
            key="new_conversation",
            icon=":material/add_comment:",
            width="stretch",
            disabled=not bool(messages),
        ):
            clear_conversation()
            st.rerun()

    if st.session_state.get("session_expired"):
        return

    st.title("Asistente de manuales", icon=":material/smart_toy:")
    source = st.session_state.get("selected_document_source")
    if source:
        st.caption(f"Manual activo: {source}")
    else:
        st.caption("Consulta tus documentos mediante una conversación.")
    render_chat(api_url, access_token, document_id)


if __name__ == "__main__":
    render_app()
