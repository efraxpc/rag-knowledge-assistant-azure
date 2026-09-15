"""Interfaz web básica para RAG Manual."""

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
from app.schemas.documents import ListDocumentsResponse, UploadDocumentResponse
from app.schemas.queries import RagAnswerResponse
from app.services.file_ingestion import MAX_UPLOAD_BYTES
from app.ui_auth import require_login

SUPPORTED_FILE_TYPES = ["pdf", "txt", "md"]


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
        st.header("Configuración")
        # El destino del token lo fija el despliegue, no un campo editable del usuario.
        api_url = get_settings().api_base_url

        if st.button("Actualizar estado", width="stretch"):
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
        st.session_state.pop("last_question", None)
        st.session_state.pop("last_answer", None)
    if st.button("Procesar y guardar", type="primary"):
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


def render_documents(api_url: str, access_token: str) -> str | None:
    """Muestra documentos persistidos y devuelve el seleccionado para consultar."""
    st.subheader("Documentos subidos")
    if st.button("Actualizar documentos", key="refresh_documents"):
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

    # Search puede tardar en mostrar una carga recién confirmada por la API.
    upload_result = st.session_state.get("upload_result")
    if upload_result and all(
        document.document_id != upload_result["document_id"] for document in documents
    ):
        documents.append(
            DocumentSummary(
                document_id=upload_result["document_id"],
                source=upload_result["source"],
                indexed_chunks=upload_result["indexed_chunks"],
            )
        )
    if not documents:
        st.info("Todavía no hay documentos guardados. Sube uno para comenzar.")
        st.session_state.pop("document_selection", None)
        st.session_state.pop("answer_document_id", None)
        st.session_state.pop("last_question", None)
        st.session_state.pop("last_answer", None)
        return None

    st.dataframe(
        [
            {"Documento": document.source, "Fragmentos": document.indexed_chunks}
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
    if st.session_state.get("answer_document_id") != document_id:
        st.session_state["answer_document_id"] = document_id
        st.session_state.pop("last_question", None)
        st.session_state.pop("last_answer", None)
    return document_id


def render_app() -> None:
    """Renderiza la aplicación Streamlit."""
    st.set_page_config(
        page_title="RAG Manual",
        page_icon="📚",
        layout="centered",
    )

    access_token = require_login()
    if access_token is None:
        return

    st.title("📚 RAG Manual")
    st.write("Sube un documento o selecciona uno guardado para consultar su contenido.")
    if render_session_expired():
        return

    st.subheader("Subir documentos")
    manual = st.file_uploader(
        "Carga un archivo",
        type=SUPPORTED_FILE_TYPES,
        help="PDF con texto, TXT y Markdown. Máximo 10 MiB; sin OCR.",
    )
    api_url = render_sidebar()

    if manual is None:
        st.session_state.pop("upload_selection", None)
        st.session_state.pop("upload_result", None)
        st.info("Selecciona un documento para comenzar.")
    else:
        st.write(f"Manual seleccionado: **{manual.name}**")
        st.caption(f"{manual.size / 1024:.1f} KB")
        render_document_upload(manual, api_url, access_token)

    if st.session_state.get("session_expired"):
        return
    document_id = render_documents(api_url, access_token)
    if st.session_state.get("session_expired"):
        return

    st.subheader("Haz una pregunta")
    with st.form("question_form"):
        question = st.text_area(
            "Pregunta",
            placeholder="Por ejemplo: ¿Cómo realizo el mantenimiento preventivo?",
            height=120,
            disabled=document_id is None,
        )
        submitted = st.form_submit_button(
            "Consultar",
            type="primary",
            width="stretch",
            disabled=document_id is None,
        )

    if submitted and document_id is not None:
        if not question.strip():
            st.warning("Escribe una pregunta antes de continuar.")
        else:
            st.session_state["last_question"] = question.strip()
            st.session_state.pop("last_answer", None)
            with st.spinner("Buscando en el manual y generando la respuesta…"):
                try:
                    result = ask_question(
                        api_url,
                        question.strip(),
                        access_token=access_token,
                        document_id=document_id,
                    )
                except QuestionSessionExpiredError:
                    st.session_state["session_expired"] = True
                    render_session_expired()
                except QuestionError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["last_answer"] = result.model_dump()

    last_question = st.session_state.get("last_question")
    if last_question:
        st.caption("Consulta más reciente")
        st.markdown(f"> {last_question}")
    last_answer = st.session_state.get("last_answer")
    if last_answer:
        st.markdown(last_answer["answer"])


if __name__ == "__main__":
    render_app()
