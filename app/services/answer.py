"""Puerta de entrada común al grafo para la API y la evaluación offline."""

from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack

from app.rag.contracts import TextChunkStore, TextCompletionClient
from app.rag.models import RagAnswer, TextQuery
from app.services.answer_graph import (
    NO_CONTEXT_ANSWER as NO_CONTEXT_ANSWER,
)
from app.services.answer_graph import (
    SYSTEM_PROMPT as SYSTEM_PROMPT,
)
from app.services.answer_graph import (
    AnswerGraph,
    AnswerGraphOptions,
)

CompletionClientFactory = Callable[[], AbstractContextManager[TextCompletionClient]]


class AnswerService:
    def __init__(
        self,
        store: TextChunkStore,
        completion_client: TextCompletionClient | None = None,
        *,
        completion_client_factory: CompletionClientFactory | None = None,
        options: AnswerGraphOptions | None = None,
    ) -> None:
        if (completion_client is None) == (completion_client_factory is None):
            raise ValueError("Proporciona un cliente o una fábrica de clientes.")
        self._store = store
        self._completion_client = completion_client
        self._completion_client_factory = completion_client_factory
        self._options = options or AnswerGraphOptions()

    def answer(self, query: TextQuery) -> RagAnswer:
        # Cada pregunta tiene su cliente y cierre, incluso si el grafo falla.
        # La fábrica OBO no se invoca hasta que generate la necesita.
        with ExitStack() as stack:
            client = self._completion_client

            def complete(system_prompt: str, user_prompt: str) -> str:
                nonlocal client
                if client is None:
                    assert self._completion_client_factory is not None
                    client = stack.enter_context(self._completion_client_factory())
                return client.complete(
                    system_prompt=system_prompt, user_prompt=user_prompt
                )

            graph = AnswerGraph(self._store, complete, self._options)
            return graph.run(query)
