"""Adaptación de los evaluadores RAG oficiales de Azure AI Evaluation."""

from importlib.metadata import version
from typing import Any, Protocol
from urllib.parse import urlsplit

from azure.ai.evaluation import GroundednessEvaluator, RelevanceEvaluator
from azure.core.credentials import TokenCredential
from pydantic import ValidationError

from app.evaluation.models import (
    AzureRagAssessment,
    EvaluationCase,
    MetricEvaluation,
)

AZURE_EVALUATION_SDK_VERSION = version("azure-ai-evaluation")
AZURE_OPENAI_EVALUATION_API_VERSION = "2024-10-21"


class Evaluator(Protocol):
    def __call__(self, **kwargs: str) -> dict[str, Any]: ...


class AzureEvaluatorError(RuntimeError):
    """Los evaluadores Azure no produjeron métricas utilizables."""


def format_context(case: EvaluationCase) -> str:
    """Conserva la procedencia al concatenar los fragmentos para Azure."""
    fragments: list[str] = []
    for fragment in case.context:
        location = fragment.source
        if fragment.page is not None:
            location = f"{location}, p. {fragment.page}"
        fragments.append(f"[{location}]\n{fragment.content}")
    return "\n\n".join(fragments)


def parse_metric(result: dict[str, Any], name: str) -> MetricEvaluation:
    try:
        return MetricEvaluation(
            score=result[f"{name}_score"],
            reason=result[f"{name}_reason"],
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise AzureEvaluatorError(
            f"Azure AI Evaluation devolvió una métrica {name} incompatible."
        ) from exc


class AzureRagEvaluators:
    """Ejecuta GroundednessEvaluator y RelevanceEvaluator con Entra ID."""

    def __init__(
        self,
        *,
        endpoint: str,
        deployment: str,
        credential: TokenCredential,
        threshold: int,
    ) -> None:
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "endpoint debe ser una URL HTTPS de recurso, sin ruta ni query"
            )
        if not deployment.strip():
            raise ValueError("deployment no puede estar vacío")
        model_config = {
            "azure_endpoint": endpoint.rstrip("/"),
            "azure_deployment": deployment,
            "api_version": AZURE_OPENAI_EVALUATION_API_VERSION,
        }
        evaluator_options = {
            "credential": credential,
            "threshold": threshold,
            "is_reasoning_model": True,
        }
        self._groundedness: Evaluator = GroundednessEvaluator(
            model_config, **evaluator_options
        )
        self._relevance: Evaluator = RelevanceEvaluator(
            model_config, **evaluator_options
        )

    def evaluate(self, case: EvaluationCase) -> AzureRagAssessment:
        try:
            groundedness = self._groundedness(
                query=case.question,
                response=case.answer,
                context=format_context(case),
            )
            relevance = self._relevance(
                query=case.question,
                response=case.answer,
            )
            return AzureRagAssessment(
                groundedness=parse_metric(groundedness, "groundedness"),
                relevance=parse_metric(relevance, "relevance"),
            )
        except AzureEvaluatorError:
            raise
        except Exception as exc:
            raise AzureEvaluatorError(
                "Azure AI Evaluation no pudo evaluar la respuesta."
            ) from exc
