"""Modelos de evaluación para Azure evaluators y la rúbrica del dominio."""

from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SourceReference = Annotated[str, Field(min_length=1, max_length=512)]
Finding = Annotated[str, Field(min_length=1, max_length=1_000)]
MAX_CONTEXT_CHARACTERS = 48_000


class EvaluationContext(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=12_000)
    source: str = Field(min_length=1, max_length=512)
    page: int | None = Field(default=None, ge=1)


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=4_000)
    answer: str = Field(min_length=1, max_length=16_000)
    context: list[EvaluationContext] = Field(max_length=20)
    expected_answer: str | None = Field(default=None, min_length=1, max_length=16_000)
    expected_sources: list[SourceReference] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_total_context_size(self) -> Self:
        if sum(len(fragment.content) for fragment in self.context) > (
            MAX_CONTEXT_CHARACTERS
        ):
            raise ValueError(
                f"El contexto no puede superar {MAX_CONTEXT_CHARACTERS} caracteres."
            )
        return self


class EvaluationScenario(BaseModel):
    """Pregunta y expectativas que debe ejecutar la versión candidata."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=4_000)
    expected_answer: str | None = Field(default=None, min_length=1, max_length=16_000)
    expected_sources: list[SourceReference] = Field(default_factory=list, max_length=20)
    document_source: str | None = Field(default=None, min_length=1, max_length=255)
    document_id: str | None = Field(default=None, min_length=1, max_length=512)
    top_k: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validate_document_selector(self) -> Self:
        if self.document_source is not None and self.document_id is not None:
            raise ValueError("Usa document_source o document_id, pero no ambos.")
        return self


class MetricEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    score: float = Field(ge=1, le=5, allow_inf_nan=False)
    reason: str = Field(min_length=1, max_length=4_000)


class AzureRagAssessment(BaseModel):
    """Métricas RAG calculadas por evaluadores oficiales de Azure."""

    model_config = ConfigDict(extra="forbid")

    groundedness: MetricEvaluation
    relevance: MetricEvaluation


class SupplementalJudgeAssessment(BaseModel):
    """Métricas del dominio que no cubren los evaluadores Azure seleccionados."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    completeness: MetricEvaluation
    citation_quality: MetricEvaluation
    missing_information: list[Finding] = Field(max_length=20)


class JudgeAssessment(BaseModel):
    """Evaluación unificada del SDK de Azure y la rúbrica del dominio."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    groundedness: MetricEvaluation
    relevance: MetricEvaluation
    completeness: MetricEvaluation
    citation_quality: MetricEvaluation
    missing_information: list[Finding] = Field(max_length=20)


class CaseEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    passed: bool
    assessment: JudgeAssessment


class EvaluationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=1)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    average_scores: dict[str, float]


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    rubric_version: str
    judge_deployment: str
    azure_evaluation_sdk_version: str
    azure_openai_evaluation_api_version: str
    evaluator_providers: dict[str, str]
    threshold: int = Field(ge=1, le=5)
    summary: EvaluationSummary
    results: list[CaseEvaluation]
