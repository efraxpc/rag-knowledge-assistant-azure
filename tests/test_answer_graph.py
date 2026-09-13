import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from app.core.exceptions import ApplicationError
from app.rag.models import SearchHit, TextQuery
from app.services.answer import NO_CONTEXT_ANSWER, AnswerService
from app.services.answer_graph import AnswerGraphOptions

INVALID_CITATIONS_ANSWER = (
    "No pude generar una respuesta con citas válidas para los fragmentos recuperados."
)


def hit(
    content: str = "Desconecta el equipo.",
    *,
    chunk_id: str = "chunk-1",
    document_id: str = "manual-1",
    source: str = "manual.pdf",
    page: int | None = 1,
) -> SearchHit:
    return SearchHit(
        id=chunk_id,
        document_id=document_id,
        content=content,
        source=source,
        page=page,
        score=1.0,
    )


def prompt_case(prompt: str) -> dict[str, object]:
    return json.loads(prompt.split("<rag_case>", 1)[1].split("</rag_case>", 1)[0])


def test_service_requires_exactly_one_completion_provider() -> None:
    store = Mock()
    with pytest.raises(ValueError):
        AnswerService(store)
    with pytest.raises(ValueError):
        AnswerService(store, Mock(), completion_client_factory=Mock())


def test_empty_search_reformulation_preserves_filters_and_original_question() -> None:
    store = Mock()
    store.search.side_effect = [[], [hit()]]
    completion = Mock()
    completion.complete.return_value = "Desconecta [manual.pdf, p. 1]."
    query = TextQuery(
        question="¿Cómo se reinicia el equipo?", document_id="manual-1", top_k=3
    )

    result = AnswerService(store, completion).answer(query)

    searches = [call.args[0] for call in store.search.call_args_list]
    assert len(searches) == 2
    assert searches[0] == query
    assert searches[1].question != query.question
    assert "reinicia" in searches[1].question
    assert "equipo" in searches[1].question
    assert all(search.document_id == "manual-1" for search in searches)
    assert all(search.top_k == 3 for search in searches)
    case = prompt_case(completion.complete.call_args.kwargs["user_prompt"])
    assert case["question"] == "¿Cómo se reinicia el equipo?"
    assert query.question == "¿Cómo se reinicia el equipo?"
    assert result.context == [hit()]
    completion.complete.assert_called_once()


@pytest.mark.parametrize("attempts", [1, 2])
def test_searches_stop_within_budget_without_repeating_queries(attempts: int) -> None:
    store = Mock()
    store.search.return_value = []
    factory = Mock()
    service = AnswerService(
        store,
        completion_client_factory=factory,
        options=AnswerGraphOptions(max_search_attempts=attempts),
    )

    result = service.answer(TextQuery(question="¿Cómo se reinicia el equipo?"))

    questions = [call.args[0].question for call in store.search.call_args_list]
    assert 1 <= len(questions) <= attempts
    assert len(set(questions)) == len(questions)
    assert result.answer == NO_CONTEXT_ANSWER
    assert result.context == []
    factory.assert_not_called()


def test_cannot_reformulate_single_keyword_into_duplicate_searches() -> None:
    store = Mock()
    store.search.return_value = []
    completion = Mock()

    result = AnswerService(
        store, completion, options=AnswerGraphOptions(max_search_attempts=2)
    ).answer(TextQuery(question="motor"))

    store.search.assert_called_once()
    assert result.answer == NO_CONTEXT_ANSWER
    completion.complete.assert_not_called()


def test_context_filters_document_deduplicates_and_obeys_top_k() -> None:
    first = hit("Primera versión.")
    second = hit("Segundo fragmento.", chunk_id="chunk-2", page=2)
    store = Mock()
    store.search.return_value = [
        hit("Otro documento.", document_id="otro"),
        first,
        hit("Duplicado que debe descartarse."),
        second,
        hit("Tercer fragmento.", chunk_id="chunk-3", page=3),
    ]
    completion = Mock()
    completion.complete.return_value = "Primera versión [manual.pdf, p. 1]."

    result = AnswerService(store, completion).answer(
        TextQuery(question="Pregunta", document_id="manual-1", top_k=2)
    )

    assert result.context == [first, second]
    prompt = completion.complete.call_args.kwargs["user_prompt"]
    assert "Otro documento" not in prompt
    assert "Duplicado" not in prompt
    assert "Tercer fragmento" not in prompt


def test_context_budget_truncates_copies_without_mutating_search_results() -> None:
    original = [hit("A" * 700), hit("B" * 700, chunk_id="chunk-2", page=2)]
    store = Mock()
    store.search.return_value = original
    completion = Mock()
    completion.complete.return_value = "Consulta el manual [manual.pdf, p. 1]."

    result = AnswerService(
        store,
        completion,
        options=AnswerGraphOptions(max_context_characters=1000),
    ).answer(TextQuery(question="Pregunta"))

    assert [len(chunk.content) for chunk in result.context] == [700, 300]
    assert [len(chunk.content) for chunk in original] == [700, 700]
    case = prompt_case(completion.complete.call_args.kwargs["user_prompt"])
    assert sum(len(chunk["content"]) for chunk in case["context"]) == 1000


def test_only_other_documents_is_treated_as_empty_without_opening_generator() -> None:
    store = Mock()
    store.search.return_value = [hit(document_id="other-document")]
    factory = Mock()

    result = AnswerService(
        store,
        completion_client_factory=factory,
        options=AnswerGraphOptions(max_search_attempts=1),
    ).answer(TextQuery(question="Pregunta", document_id="manual-1"))

    assert result.context == []
    assert result.answer == NO_CONTEXT_ANSWER
    factory.assert_not_called()


@pytest.mark.parametrize(
    ("page", "citation"), [(1, "[manual.pdf, p. 1]"), (None, "[manual.pdf]")]
)
def test_valid_citation_needs_one_generation(page: int | None, citation: str) -> None:
    store = Mock()
    store.search.return_value = [hit(page=page)]
    completion = Mock()
    completion.complete.return_value = f"Desconecta {citation}."

    result = AnswerService(store, completion).answer(TextQuery(question="Pregunta"))

    assert result.answer == f"Desconecta {citation}."
    completion.complete.assert_called_once()


@pytest.mark.parametrize(
    "invalid_answer",
    [
        "Desconecta el equipo.",
        "Desconecta [inventado.pdf, p. 1].",
        "Desconecta [manual.pdf, p. 9].",
        "Desconecta [manual.pdf].",
        "Desconecta [manual.pdf, p. 1] y espera [inventado.pdf, p. 1].",
    ],
)
def test_invalid_citations_are_repaired_with_another_generation(
    invalid_answer: str,
) -> None:
    store = Mock()
    store.search.return_value = [hit()]
    completion = Mock()
    completion.complete.side_effect = [
        invalid_answer,
        "Desconecta [manual.pdf, p. 1].",
    ]

    result = AnswerService(store, completion).answer(TextQuery(question="Pregunta"))

    assert result.answer == "Desconecta [manual.pdf, p. 1]."
    assert result.context == [hit()]
    assert completion.complete.call_count == 2
    initial, repair = completion.complete.call_args_list
    assert repair.kwargs["user_prompt"] != initial.kwargs["user_prompt"]
    assert prompt_case(repair.kwargs["user_prompt"])["question"] == "Pregunta"
    store.search.assert_called_once()


@pytest.mark.parametrize("attempts", [1, 2])
def test_repeated_citation_failure_abstains_at_generation_budget(attempts: int) -> None:
    store = Mock()
    store.search.return_value = [hit()]
    completion = Mock()
    completion.complete.return_value = "Respuesta sin fuentes."

    result = AnswerService(
        store,
        completion,
        options=AnswerGraphOptions(max_generation_attempts=attempts),
    ).answer(TextQuery(question="Pregunta"))

    assert result.answer == INVALID_CITATIONS_ANSWER
    assert result.context == [hit()]
    assert completion.complete.call_count == attempts


def test_citation_verification_can_be_disabled_without_repair() -> None:
    store = Mock()
    store.search.return_value = [hit()]
    completion = Mock()
    completion.complete.return_value = "Respuesta sin cita."

    result = AnswerService(
        store, completion, options=AnswerGraphOptions(verify_citations=False)
    ).answer(TextQuery(question="Pregunta"))

    assert result.answer == "Respuesta sin cita."
    completion.complete.assert_called_once()


def test_lazy_factory_is_opened_once_and_closed_after_citation_repair() -> None:
    store = Mock()
    store.search.return_value = [hit()]
    completion = Mock()
    completion.complete.side_effect = [
        "Sin citas.",
        "Desconecta [manual.pdf, p. 1].",
    ]
    lifecycle = []

    @contextmanager
    def open_client() -> Iterator[Mock]:
        lifecycle.append("open")
        try:
            yield completion
        finally:
            lifecycle.append("closed")

    factory = Mock(side_effect=open_client)
    service = AnswerService(store, completion_client_factory=factory)
    factory.assert_not_called()

    result = service.answer(TextQuery(question="Pregunta"))

    assert result.answer == "Desconecta [manual.pdf, p. 1]."
    assert lifecycle == ["open", "closed"]
    factory.assert_called_once_with()


@pytest.mark.parametrize("status", [403, 503])
def test_search_error_propagates_without_retry_or_openai(status: int) -> None:
    error = ApplicationError("Search no disponible.", status_code=status)
    store = Mock()
    store.search.side_effect = error
    factory = Mock()

    with pytest.raises(ApplicationError) as raised:
        AnswerService(store, completion_client_factory=factory).answer(
            TextQuery(question="¿Cómo se reinicia el equipo?")
        )

    assert raised.value is error
    store.search.assert_called_once()
    factory.assert_not_called()


def test_generation_error_propagates_without_retry_and_closes_client() -> None:
    error = ApplicationError("Error del generador.", status_code=502)
    store = Mock()
    store.search.return_value = [hit()]
    completion = Mock()
    completion.complete.side_effect = error
    lifecycle = []

    @contextmanager
    def open_client() -> Iterator[Mock]:
        lifecycle.append("open")
        try:
            yield completion
        finally:
            lifecycle.append("closed")

    with pytest.raises(ApplicationError) as raised:
        AnswerService(store, completion_client_factory=open_client).answer(
            TextQuery(question="Pregunta")
        )

    assert raised.value is error
    completion.complete.assert_called_once()
    assert lifecycle == ["open", "closed"]


def test_service_reuse_keeps_context_separate_between_invocations() -> None:
    store = Mock()
    store.search.side_effect = [[hit()], []]
    completion = Mock()
    completion.complete.return_value = "Desconecta [manual.pdf, p. 1]."
    service = AnswerService(
        store, completion, options=AnswerGraphOptions(max_search_attempts=1)
    )

    first = service.answer(TextQuery(question="Primera pregunta"))
    second = service.answer(TextQuery(question="Segunda pregunta"))

    assert first.context == [hit()]
    assert second.context == []
    assert second.answer == NO_CONTEXT_ANSWER
    assert store.search.call_count == 2
    completion.complete.assert_called_once()


def test_generation_budget_resets_for_each_answer_on_the_same_service() -> None:
    store = Mock()
    store.search.side_effect = [
        [hit()],
        [hit(document_id="manual-2", source="segundo.pdf")],
    ]
    completion = Mock()
    completion.complete.side_effect = [
        "Primer intento sin cita.",
        "Desconecta [manual.pdf, p. 1].",
        "Segundo intento sin cita.",
        "Enciende [segundo.pdf, p. 1].",
    ]
    service = AnswerService(store, completion)

    first = service.answer(TextQuery(question="Primera", document_id="manual-1"))
    second = service.answer(TextQuery(question="Segunda", document_id="manual-2"))

    assert first.answer == "Desconecta [manual.pdf, p. 1]."
    assert second.answer == "Enciende [segundo.pdf, p. 1]."
    assert second.context[0].document_id == "manual-2"
    assert completion.complete.call_count == 4


def test_flow_logs_include_stage_metrics_without_question_context_or_answer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = Mock()
    store.search.return_value = [hit("CONTENIDO_CONFIDENCIAL_XYZ")]
    completion = Mock()
    completion.complete.return_value = "RESPUESTA_PRIVADA_XYZ [manual.pdf, p. 1]."

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        AnswerService(store, completion).answer(
            TextQuery(question="PREGUNTA_PRIVADA_XYZ")
        )

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "rag_flow" in messages
    for field in (
        "request_id",
        "node",
        "outcome",
        "search_attempts",
        "generation_attempts",
        "duration_ms",
    ):
        assert field in messages
    assert "PREGUNTA_PRIVADA_XYZ" not in messages
    assert "CONTENIDO_CONFIDENCIAL_XYZ" not in messages
    assert "RESPUESTA_PRIVADA_XYZ" not in messages


def test_flow_tracing_can_be_disabled(caplog: pytest.LogCaptureFixture) -> None:
    store = Mock()
    store.search.return_value = []
    completion = Mock()

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        AnswerService(
            store,
            completion,
            options=AnswerGraphOptions(trace_enabled=False, max_search_attempts=1),
        ).answer(TextQuery(question="Pregunta"))

    assert not any("rag_flow" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("source", ["manual[2026].pdf", "manual.*(v1).pdf"])
def test_citations_support_filename_punctuation_without_regex_interpretation(
    source: str,
) -> None:
    store = Mock()
    store.search.return_value = [hit(source=source)]
    completion = Mock()
    completion.complete.return_value = f"Desconecta [{source}, p. 1]."

    result = AnswerService(store, completion).answer(TextQuery(question="Pregunta"))

    assert result.answer == f"Desconecta [{source}, p. 1]."
    completion.complete.assert_called_once()


def test_failed_generation_trace_counts_the_attempt_without_logging_diagnostics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = Mock()
    store.search.return_value = [hit()]
    completion = Mock()
    completion.complete.side_effect = ApplicationError(
        "DIAGNOSTICO_PRIVADO", status_code=502, code="rag_provider_error"
    )

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        with pytest.raises(ApplicationError):
            AnswerService(store, completion).answer(TextQuery(question="Pregunta"))

    record = next(
        r.getMessage() for r in caplog.records if "node=generate" in r.getMessage()
    )
    assert "generation_attempts=1" in record
    assert "outcome=rag_provider_error" in record
    assert "DIAGNOSTICO_PRIVADO" not in caplog.text
