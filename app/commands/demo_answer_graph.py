"""Recorre las ramas del RAG con datos ficticios, sin Azure ni archivos .env."""

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from typing import Any

from app.core.exceptions import ApplicationError
from app.rag.models import Chunk, SearchHit, TextQuery
from app.services.answer import AnswerService

SCENARIOS = ("success", "recovered", "empty", "repair", "invalid", "provider-error")
VALID_ANSWER = "Desconecta y vuelve a conectar el equipo [manual-demo.pdf, p. 1]."


class DemoStore:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario
        self.calls = 0

    def index_chunks(self, chunks: Sequence[Chunk]) -> None:
        raise NotImplementedError("La demo solo consulta un documento ficticio.")

    def search(self, query: TextQuery) -> list[SearchHit]:
        self.calls += 1
        if self.scenario == "empty" or (
            self.scenario == "recovered" and self.calls == 1
        ):
            return []
        return [
            SearchHit(
                id="paso-1",
                document_id="demo",
                source="manual-demo.pdf",
                page=1,
                content="Para reiniciar, desconecta y vuelve a conectar el equipo.",
                score=1,
            )
        ]


class DemoCompletionClient:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario
        self.calls = 0

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.scenario == "provider-error":
            raise ApplicationError(
                "Fallo simulado del proveedor.",
                status_code=502,
                code="rag_provider_error",
            )
        if self.scenario == "invalid" or (
            self.scenario == "repair" and self.calls == 1
        ):
            return "Reinicia el equipo [fuente-inventada.pdf, p. 99]."
        return VALID_ANSWER


def run_scenario(scenario: str) -> dict[str, Any]:
    store = DemoStore(scenario)
    client = DemoCompletionClient(scenario)
    service = AnswerService(store, client)
    try:
        result = service.answer(
            TextQuery(question="¿Cómo se reinicia el equipo?", document_id="demo")
        ).model_dump()
    except ApplicationError as exc:
        result = {"error": {"code": exc.code, "message": exc.message}}
    result["demo_calls"] = {"search": store.calls, "generation": client.calls}
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=(*SCENARIOS, "all"), default="all")
    args = parser.parse_args(argv)
    logger = logging.getLogger("uvicorn.error")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    # Guardar y restaurar la configuración también permite probar la CLI en proceso.
    previous = (logger.level, logger.propagate, logger.handlers[:])
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        scenarios = SCENARIOS if args.scenario == "all" else (args.scenario,)
        for scenario in scenarios:
            print(f"\nEscenario: {scenario}")
            print(json.dumps(run_scenario(scenario), ensure_ascii=False, indent=2))
    finally:
        logger.setLevel(previous[0])
        logger.propagate = previous[1]
        logger.handlers = previous[2]
        handler.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
