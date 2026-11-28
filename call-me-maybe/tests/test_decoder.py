"""Unit tests for the constrained decoding engine.

The tests use a scripted fake model (see ``fake_model.py``) so the state
machines are validated deterministically, without downloading weights.
"""
import json
from pathlib import Path
from typing import Any

import pytest

from src.decoder import (
    ConstrainedDecoder,
    _is_complete_number,
    _is_number_text,
    _is_string_text,
    _number_can_extend,
)
from src.models import FunctionSpec, ParameterSpec
from src.vocab import Vocab

from .fake_model import FAKE_VOCAB, FakeModel


@pytest.fixture
def vocab(tmp_path: Path) -> Vocab:
    path = tmp_path / "vocab.json"
    path.write_text(json.dumps(FAKE_VOCAB), encoding="utf-8")
    return Vocab(path)


def test_is_number_text() -> None:
    assert _is_number_text("42")
    assert _is_number_text("-4.5")
    assert not _is_number_text("")
    assert not _is_number_text("4,2")
    assert not _is_number_text('4"')


def test_is_string_text() -> None:
    assert _is_string_text("hello")
    assert _is_string_text("a b")
    assert not _is_string_text("")
    assert not _is_string_text('a"b')
    assert not _is_string_text("a\\b")
    assert not _is_string_text("a\nb")


def test_number_can_extend_rejects_leading_zero() -> None:
    assert _number_can_extend("", "4", integer_only=False)
    assert _number_can_extend("", "-", integer_only=False)
    assert _number_can_extend("-", "4", integer_only=False)
    assert not _number_can_extend("0", "4", integer_only=False)
    assert _number_can_extend("0", ".", integer_only=False)
    assert not _number_can_extend("4.", ".", integer_only=False)
    assert not _number_can_extend("4", ".", integer_only=True)


def test_is_complete_number() -> None:
    assert _is_complete_number("0")
    assert _is_complete_number("-0")
    assert _is_complete_number("42")
    assert _is_complete_number("4.2")
    assert not _is_complete_number("")
    assert not _is_complete_number("-")
    assert not _is_complete_number("4.")


def test_decode_number_stops_when_model_moves_on(vocab: Vocab) -> None:
    model = FakeModel(vocab, ["4", "2", ","])
    decoder = ConstrainedDecoder(model, vocab)
    assert decoder._decode_number("a: ", integer_only=False) == "42"


def test_decode_number_negative_and_float(vocab: Vocab) -> None:
    model = FakeModel(vocab, ["-", "4", ".", "2", ","])
    decoder = ConstrainedDecoder(model, vocab)
    assert decoder._decode_number("a: ", integer_only=False) == "-4.2"


def test_decode_number_integer_only(vocab: Vocab) -> None:
    model = FakeModel(vocab, ["4", "2", ","])
    decoder = ConstrainedDecoder(model, vocab)
    assert decoder._decode_number("a: ", integer_only=True) == "42"


def test_decode_number_empty_falls_back(vocab: Vocab) -> None:
    model = FakeModel(vocab, [","])
    decoder = ConstrainedDecoder(model, vocab)
    assert decoder._decode_number("a: ", integer_only=False) == ""


def test_decode_string_closes_on_quote(vocab: Vocab) -> None:
    model = FakeModel(vocab, ["sh", "rek", '"'])
    decoder = ConstrainedDecoder(model, vocab)
    assert decoder._decode_string("Greet shrek", "name") == "shrek"


def test_decode_name_disambiguates_with_logits(vocab: Vocab) -> None:
    model = FakeModel(vocab, ["fn_a", '"'])
    decoder = ConstrainedDecoder(model, vocab)
    functions = [
        FunctionSpec(name="fn_a"),
        FunctionSpec(name="fn_b"),
    ]
    assert decoder._decode_name("base", functions) == "fn_a"


def test_generate_call_string_parameter(vocab: Vocab) -> None:
    spec = FunctionSpec(name="fn_a", parameters={"x": ParameterSpec(type="string")})
    model = FakeModel(vocab, ["sh", "rek", '"'])
    decoder = ConstrainedDecoder(model, vocab)
    generated, parameters = decoder.generate_call("Greet shrek", [spec])
    assert parameters == {"x": "shrek"}
    parsed: dict[str, Any] = json.loads(generated)
    assert parsed == {"name": "fn_a", "parameters": {"x": "shrek"}}


def test_generate_call_number_parameter(vocab: Vocab) -> None:
    spec = FunctionSpec(name="fn_a", parameters={"x": ParameterSpec(type="number")})
    model = FakeModel(vocab, ["4", "2", ","])
    decoder = ConstrainedDecoder(model, vocab)
    generated, parameters = decoder.generate_call("Give me 42", [spec])
    assert parameters == {"x": 42}
    parsed: dict[str, Any] = json.loads(generated)
    assert parsed == {"name": "fn_a", "parameters": {"x": 42}}


def test_generate_call_boolean_and_no_parameters(vocab: Vocab) -> None:
    spec = FunctionSpec(name="fn_a", parameters={"x": ParameterSpec(type="boolean")})
    model = FakeModel(vocab, ["fn_a", "true"])
    decoder = ConstrainedDecoder(model, vocab)
    generated, parameters = decoder.generate_call("Set the flag", [spec])
    assert parameters == {"x": True}
    assert json.loads(generated)["parameters"] == {"x": True}

    empty = FunctionSpec(name="fn_b")
    model = FakeModel(vocab, ["fn_b"])
    decoder = ConstrainedDecoder(model, vocab)
    generated, parameters = decoder.generate_call("Do nothing", [empty])
    assert parameters == {}
    assert json.loads(generated) == {"name": "fn_b", "parameters": {}}
