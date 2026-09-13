import logging

import pytest

from app.commands.demo_answer_graph import VALID_ANSWER, main, run_scenario
from app.services.answer_graph import INVALID_CITATIONS_ANSWER, NO_CONTEXT_ANSWER


@pytest.mark.parametrize(
    ("scenario", "search_calls", "generation_calls", "answer"),
    [
        ("success", 1, 1, VALID_ANSWER),
        ("recovered", 2, 1, VALID_ANSWER),
        ("empty", 2, 0, NO_CONTEXT_ANSWER),
        ("repair", 1, 2, VALID_ANSWER),
        ("invalid", 1, 2, INVALID_CITATIONS_ANSWER),
    ],
)
def test_offline_scenarios_reach_expected_branches(
    scenario: str, search_calls: int, generation_calls: int, answer: str
) -> None:
    result = run_scenario(scenario)
    assert result["answer"] == answer
    assert result["demo_calls"] == {
        "search": search_calls,
        "generation": generation_calls,
    }


def test_provider_error_demo_does_not_retry_generation() -> None:
    result = run_scenario("provider-error")
    assert result["error"]["code"] == "rag_provider_error"
    assert result["demo_calls"] == {"search": 1, "generation": 1}


def test_cli_displays_branches_and_restores_logging(
    capsys: pytest.CaptureFixture[str],
) -> None:
    logger = logging.getLogger("uvicorn.error")
    previous = (logger.level, logger.propagate, logger.handlers[:])
    assert main(["--scenario", "all"]) == 0
    text = capsys.readouterr().out
    assert "Escenario: recovered" in text
    assert "node=rewrite_query" in text
    assert "node=repair" in text
    assert "rag_provider_error" in text
    assert (logger.level, logger.propagate, logger.handlers) == previous
