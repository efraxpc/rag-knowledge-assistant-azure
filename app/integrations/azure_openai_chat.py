"""Cliente mínimo de Azure OpenAI para generar respuestas RAG."""

import json
from typing import Any

import httpx
from azure.core.credentials import TokenCredential
from azure.core.exceptions import AzureError

from app.core.exceptions import ApplicationError

# El endpoint OpenAI v1 usa el permiso delegado de Microsoft Cognitive Services.
AZURE_AI_SCOPE = "https://cognitiveservices.azure.com/.default"


class RagProviderError(ApplicationError):
    """Azure OpenAI no pudo producir una respuesta RAG utilizable."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            status_code=502,
            code="rag_provider_error",
        )


def normalize_answer(content: str) -> str:
    """Extrae texto plano cuando el modelo envuelve la respuesta en JSON."""
    normalized = content.strip()
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        return normalized

    if isinstance(payload, dict) and set(payload) == {"answer"}:
        answer = payload["answer"]
        if not isinstance(answer, str) or not answer.strip():
            raise RagProviderError(
                "Azure OpenAI devolvió una respuesta RAG incompatible."
            )
        return answer.strip()
    return normalized


class AzureOpenAIChatClient:
    def __init__(
        self,
        *,
        endpoint: str,
        deployment: str,
        credential: TokenCredential,
        http_client: httpx.Client,
        max_completion_tokens: int = 8_000,
        reasoning_effort: str = "minimal",
    ) -> None:
        base_url = httpx.URL(endpoint)
        if (
            base_url.scheme != "https"
            or not base_url.host
            or base_url.path not in {"", "/"}
            or base_url.query
            or base_url.fragment
        ):
            raise ValueError(
                "endpoint debe ser una URL HTTPS de recurso, sin ruta ni query"
            )
        if not deployment.strip():
            raise ValueError("deployment no puede estar vacío")
        if not 1 <= max_completion_tokens <= 100_000:
            raise ValueError("max_completion_tokens debe estar entre 1 y 100000")
        if reasoning_effort not in {"minimal", "low", "medium", "high"}:
            raise ValueError("reasoning_effort no es compatible")
        self._url = f"{str(base_url).rstrip('/')}/openai/v1/chat/completions"
        self._deployment = deployment
        self._credential = credential
        self._http_client = http_client
        self._max_completion_tokens = max_completion_tokens
        self._reasoning_effort = reasoning_effort

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        try:
            token = self._credential.get_token(AZURE_AI_SCOPE).token
        except AzureError as exc:
            raise RagProviderError(
                "No se pudo obtener un token de Entra ID para generar la respuesta."
            ) from exc

        try:
            response = self._http_client.post(
                self._url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._deployment,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_completion_tokens": self._max_completion_tokens,
                    "reasoning_effort": self._reasoning_effort,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            status = (
                exc.response.status_code
                if isinstance(exc, httpx.HTTPStatusError)
                else None
            )
            suffix = f" (HTTP {status})" if status is not None else ""
            raise RagProviderError(
                f"Azure OpenAI no pudo generar la respuesta RAG{suffix}."
            ) from exc

        try:
            payload: Any = response.json()
            choice = payload["choices"][0]
            message = choice["message"]
            if message.get("refusal"):
                raise RagProviderError("El modelo generador rechazó responder el caso.")
            content = message["content"]
        except RagProviderError:
            raise
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise RagProviderError(
                "Azure OpenAI devolvió una respuesta RAG incompatible."
            ) from exc

        if not isinstance(content, str) or not content.strip():
            if choice.get("finish_reason") == "length":
                raise RagProviderError(
                    "Azure OpenAI agotó el presupuesto de salida antes de producir "
                    "una respuesta."
                )
            raise RagProviderError(
                "Azure OpenAI devolvió una respuesta RAG incompatible."
            )
        return normalize_answer(content)
