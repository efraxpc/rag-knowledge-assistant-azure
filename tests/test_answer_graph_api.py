from dataclasses import dataclass, field
from unittest.mock import MagicMock, Mock

import pytest
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
from fastapi.testclient import TestClient
from httpx import Response

from app import main
from app.core import resources
from app.core.auth import require_user
from app.integrations.azure_openai_chat import AZURE_AI_SCOPE, RagProviderError
from app.services.answer import NO_CONTEXT_ANSWER
from tests.auth_helpers import authenticated_user, entra_settings


@dataclass
class AzureDoubles:
    search_client: MagicMock
    search_factory: Mock
    http_client: MagicMock
    http_factory: Mock
    completion: Mock
    completion_factory: Mock
    credentials: list[MagicMock] = field(default_factory=list)
    credential_factory: Mock = field(default_factory=Mock)


@pytest.fixture
def azure(monkeypatch: pytest.MonkeyPatch) -> AzureDoubles:
    search_client = MagicMock()
    search_client.__enter__.return_value = search_client
    search_client.search.return_value = [
        {
            "chunk_id": "chunk-1",
            "document_id": "manual-1",
            "content": "Desconecta el equipo antes del mantenimiento.",
            "source": "manual.pdf",
            "page": 1,
            "@search.score": 1.0,
        }
    ]
    http_client = MagicMock()
    http_client.__enter__.return_value = http_client
    completion = Mock()
    completion.complete.return_value = "Desconecta [manual.pdf, p. 1]."
    doubles = AzureDoubles(
        search_client=search_client,
        search_factory=Mock(return_value=search_client),
        http_client=http_client,
        http_factory=Mock(return_value=http_client),
        completion=completion,
        completion_factory=Mock(return_value=completion),
    )

    def new_credential(**kwargs: object) -> MagicMock:
        credential = MagicMock()
        credential.__enter__.return_value = credential
        doubles.credentials.append(credential)
        return credential

    doubles.credential_factory.side_effect = new_credential
    monkeypatch.setattr(resources, "OnBehalfOfCredential", doubles.credential_factory)
    monkeypatch.setattr(resources, "SearchClient", doubles.search_factory)
    monkeypatch.setattr(resources.httpx, "Client", doubles.http_factory)
    monkeypatch.setattr(resources, "AzureOpenAIChatClient", doubles.completion_factory)
    return doubles


def api_client(
    monkeypatch: pytest.MonkeyPatch, *, generator_configured: bool = True
) -> TestClient:
    settings = entra_settings(
        azure_search_index_name=None,
        azure_search_vector_dimensions=None,
        azure_openai_endpoint=(
            "https://example.openai.azure.com" if generator_configured else None
        ),
        azure_openai_chat_deployment=("candidate-v1" if generator_configured else None),
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    app = main.create_app()
    app.dependency_overrides[require_user] = authenticated_user
    return TestClient(app)


def ask(client: TestClient) -> Response:
    return client.post(
        "/api/v1/queries/answer",
        json={"question": "¿Qué debo hacer?", "document_id": "manual-1"},
    )


def test_empty_search_skips_openai_even_without_generator_configuration(
    monkeypatch: pytest.MonkeyPatch, azure: AzureDoubles
) -> None:
    azure.search_client.search.return_value = []

    with api_client(monkeypatch, generator_configured=False) as client:
        response = ask(client)

    assert response.status_code == 200
    assert response.json()["answer"] == NO_CONTEXT_ANSWER
    assert response.json()["context"] == []
    azure.completion_factory.assert_not_called()
    azure.http_factory.assert_not_called()
    azure.completion.complete.assert_not_called()
    assert len(azure.credentials) == 1
    azure.credentials[0].get_token.assert_called_once_with(resources.SEARCH_SCOPE)
    azure.credentials[0].__exit__.assert_called_once()
    azure.search_client.__exit__.assert_called_once()
    for call in azure.search_client.search.call_args_list:
        assert call.kwargs["filter"] == "document_id eq 'manual-1'"


def test_context_requires_generator_and_preserves_configuration_error(
    monkeypatch: pytest.MonkeyPatch, azure: AzureDoubles
) -> None:
    with api_client(monkeypatch, generator_configured=False) as client:
        response = ask(client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "rag_generator_not_configured"
    azure.completion_factory.assert_not_called()
    assert len(azure.credentials) == 1
    azure.credentials[0].__exit__.assert_called_once()
    azure.search_client.__exit__.assert_called_once()


def test_success_uses_same_user_for_search_and_openai_and_closes_clients(
    monkeypatch: pytest.MonkeyPatch, azure: AzureDoubles
) -> None:
    with api_client(monkeypatch) as client:
        response = ask(client)

    assert response.status_code == 200
    assert response.json()["answer"] == "Desconecta [manual.pdf, p. 1]."
    assert response.json()["context"][0]["source"] == "manual.pdf"
    assert len(azure.credentials) == 2
    for call in azure.credential_factory.call_args_list:
        assert call.kwargs["user_assertion"] == authenticated_user().assertion
        assert call.kwargs["client_secret"] == "test-api-secret"
    azure.credentials[0].get_token.assert_called_once_with(resources.SEARCH_SCOPE)
    azure.credentials[1].get_token.assert_called_once_with(AZURE_AI_SCOPE)
    assert azure.search_factory.call_args.kwargs["credential"] is azure.credentials[0]
    assert (
        azure.completion_factory.call_args.kwargs["credential"] is azure.credentials[1]
    )
    azure.completion.complete.assert_called_once()
    for credential in azure.credentials:
        credential.__exit__.assert_called_once()
    azure.search_client.__exit__.assert_called_once()
    azure.http_client.__exit__.assert_called_once()


def test_search_rbac_failure_propagates_without_openai_or_identity_retry(
    monkeypatch: pytest.MonkeyPatch, azure: AzureDoubles
) -> None:
    denied = HttpResponseError("private provider diagnostic")
    denied.status_code = 403
    azure.search_client.search.side_effect = denied

    with api_client(monkeypatch) as client:
        response = ask(client)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "search_access_denied"
    assert "private provider diagnostic" not in response.text
    azure.search_client.search.assert_called_once()
    azure.completion_factory.assert_not_called()
    assert len(azure.credentials) == 1
    azure.credentials[0].__exit__.assert_called_once()
    azure.search_client.__exit__.assert_called_once()


def test_openai_obo_failure_propagates_and_closes_credentials(
    monkeypatch: pytest.MonkeyPatch, azure: AzureDoubles
) -> None:
    search_credential, openai_credential = MagicMock(), MagicMock()
    for credential in (search_credential, openai_credential):
        credential.__enter__.return_value = credential
    openai_credential.get_token.side_effect = ClientAuthenticationError(
        "private provider diagnostic"
    )
    azure.credential_factory.side_effect = [search_credential, openai_credential]

    with api_client(monkeypatch) as client:
        response = ask(client)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "delegated_authentication_failed"
    assert "private provider diagnostic" not in response.text
    assert azure.credential_factory.call_count == 2
    azure.completion_factory.assert_not_called()
    azure.http_factory.assert_not_called()
    search_credential.__exit__.assert_called_once()
    openai_credential.__exit__.assert_called_once()
    azure.search_client.__exit__.assert_called_once()


def test_generation_failure_preserves_error_and_closes_clients(
    monkeypatch: pytest.MonkeyPatch, azure: AzureDoubles
) -> None:
    azure.completion.complete.side_effect = RagProviderError("No se pudo generar.")

    with api_client(monkeypatch) as client:
        response = ask(client)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "rag_provider_error"
    azure.completion.complete.assert_called_once()
    for credential in azure.credentials:
        credential.__exit__.assert_called_once()
    azure.search_client.__exit__.assert_called_once()
    azure.http_client.__exit__.assert_called_once()
