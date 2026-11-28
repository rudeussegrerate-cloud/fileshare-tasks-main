"""Unit tests for the pipeline orchestration and its fallbacks."""
import json
from pathlib import Path
from typing import Any

import pytest

from src.decoder import ConstrainedDecoder
from src.models import FunctionSpec, ParameterSpec, PromptRequest
from src.pipeline import fallback_call, process_prompt, run_pipeline
from src.vocab import Vocab

from .fake_model import FAKE_VOCAB, FakeModel


@pytest.fixture
def vocab(tmp_path: Path) -> Vocab:
    path = tmp_path / "vocab.json"
    path.write_text(json.dumps(FAKE_VOCAB), encoding="utf-8")
    return Vocab(path)


@pytest.fixture
def functions() -> list[FunctionSpec]:
    return [
        FunctionSpec(
            name="fn_a",
            description="Does a.",
            parameters={"x": ParameterSpec(type="number")},
        ),
        FunctionSpec(
            name="fn_b",
            description="Does b.",
            parameters={"s": ParameterSpec(type="string")},
        ),
    ]


def test_fallback_call_uses_first_function(
    functions: list[FunctionSpec],
) -> None:
    call = fallback_call("anything", functions)
    assert call.name == "fn_a"
    assert call.parameters == {"x": 0}


def test_process_prompt_succeeds(
    vocab: Vocab, functions: list[FunctionSpec]
) -> None:
    model = FakeModel(vocab, ["fn_a", "4", "2", ","])
    decoder = ConstrainedDecoder(model, vocab)
    call = process_prompt(decoder, PromptRequest(prompt="Give 42"), functions)
    assert call.prompt == "Give 42"
    assert call.name == "fn_a"
    assert call.parameters == {"x": 42}


def test_process_prompt_falls_back_on_model_failure(
    vocab: Vocab, functions: list[FunctionSpec]
) -> None:
    model = FakeModel(vocab, [])
    model.get_logits_from_input_ids = _raise  # type: ignore[method-assign]
    decoder = ConstrainedDecoder(model, vocab)
    call = process_prompt(decoder, PromptRequest(prompt="anything"), functions)
    assert call.name == "fn_a"
    assert call.parameters == {"x": 0}


def _raise(input_ids: list[int]) -> list[float]:
    raise RuntimeError("model exploded")


def test_run_pipeline_covers_every_prompt(
    vocab: Vocab, functions: list[FunctionSpec]
) -> None:
    model = FakeModel(vocab, [])
    decoder = ConstrainedDecoder(model, vocab)
    requests = [PromptRequest(prompt="one"), PromptRequest(prompt="two")]
    calls = run_pipeline(decoder, requests, functions)
    assert [call.prompt for call in calls] == ["one", "two"]
    dumped: list[dict[str, Any]] = [call.model_dump() for call in calls]
    for entry in dumped:
        assert set(entry) == {"prompt", "name", "parameters"}
