from unittest.mock import Mock

import pytest

from app.evaluation.models import EvaluationCase
from app.integrations import azure_rag_evaluators
from app.integrations.azure_rag_evaluators import (
    AzureEvaluatorError,
    AzureRagEvaluators,
    format_context,
    parse_metric,
)


@pytest.fixture
def case() -> EvaluationCase:
    return EvaluationCase(
        id="case-1",
        question="¿Cómo hago el mantenimiento?",
        answer="Desconecta el equipo [manual.pdf, p. 2].",
        context=[
            {
                "content": "Desconecta el equipo antes de abrirlo.",
                "source": "manual.pdf",
                "page": 2,
            },
            {"content": "Utiliza guantes.", "source": "seguridad.txt"},
        ],
    )


def test_runs_official_evaluators_with_entra_id(
    case: EvaluationCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    groundedness = Mock(
        return_value={
            "groundedness_score": 5.0,
            "groundedness_reason": "La respuesta está respaldada.",
        }
    )
    relevance = Mock(
        return_value={
            "relevance_score": 4.0,
            "relevance_reason": "La respuesta atiende la pregunta.",
        }
    )
    groundedness_factory = Mock(return_value=groundedness)
    relevance_factory = Mock(return_value=relevance)
    monkeypatch.setattr(
        azure_rag_evaluators, "GroundednessEvaluator", groundedness_factory
    )
    monkeypatch.setattr(azure_rag_evaluators, "RelevanceEvaluator", relevance_factory)
    credential = Mock()

    evaluators = AzureRagEvaluators(
        endpoint="https://example.openai.azure.com/",
        deployment="judge-v1",
        credential=credential,
        threshold=4,
    )
    result = evaluators.evaluate(case)

    model_config = {
        "azure_endpoint": "https://example.openai.azure.com",
        "azure_deployment": "judge-v1",
        "api_version": "2024-10-21",
    }
    options = {
        "credential": credential,
        "threshold": 4,
        "is_reasoning_model": True,
    }
    groundedness_factory.assert_called_once_with(model_config, **options)
    relevance_factory.assert_called_once_with(model_config, **options)
    groundedness.assert_called_once_with(
        query=case.question,
        response=case.answer,
        context=(
            "[manual.pdf, p. 2]\nDesconecta el equipo antes de abrirlo.\n\n"
            "[seguridad.txt]\nUtiliza guantes."
        ),
    )
    relevance.assert_called_once_with(query=case.question, response=case.answer)
    assert result.groundedness.score == 5
    assert result.relevance.score == 4


def test_format_context_accepts_no_fragments() -> None:
    case = EvaluationCase(
        id="case", question="Pregunta", answer="Respuesta", context=[]
    )
    assert format_context(case) == ""


@pytest.mark.parametrize(
    "result",
    [
        {},
        {"groundedness_score": None, "groundedness_reason": "Razón"},
        {"groundedness_score": 6, "groundedness_reason": "Razón"},
        {"groundedness_score": 4, "groundedness_reason": ""},
    ],
)
def test_rejects_invalid_metric(result: dict[str, object]) -> None:
    with pytest.raises(AzureEvaluatorError, match="groundedness"):
        parse_metric(result, "groundedness")


def test_hides_provider_failure(
    case: EvaluationCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    evaluator = Mock(side_effect=RuntimeError("respuesta privada"))
    monkeypatch.setattr(
        azure_rag_evaluators, "GroundednessEvaluator", Mock(return_value=evaluator)
    )
    monkeypatch.setattr(
        azure_rag_evaluators, "RelevanceEvaluator", Mock(return_value=Mock())
    )
    evaluators = AzureRagEvaluators(
        endpoint="https://example.openai.azure.com",
        deployment="judge-v1",
        credential=Mock(),
        threshold=4,
    )
    with pytest.raises(AzureEvaluatorError, match="no pudo evaluar") as error:
        evaluators.evaluate(case)
    assert "privada" not in str(error.value)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.openai.azure.com",
        "https://example.openai.azure.com/openai/v1",
        "https://example.openai.azure.com?api-version=preview",
    ],
)
def test_rejects_endpoint_that_could_misroute_token(endpoint: str) -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        AzureRagEvaluators(
            endpoint=endpoint,
            deployment="judge",
            credential=Mock(),
            threshold=4,
        )
