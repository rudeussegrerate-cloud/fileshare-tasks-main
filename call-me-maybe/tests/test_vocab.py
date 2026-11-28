"""Unit tests for the vocabulary decoding utilities."""
import json
from pathlib import Path


from src.vocab import Vocab, token_to_text


def test_token_to_text_maps_space() -> None:
    assert token_to_text("Ġworld") == " world"


def test_token_to_text_maps_newline() -> None:
    assert token_to_text("Ċ") == "\n"


def test_token_to_text_plain_ascii() -> None:
    assert token_to_text('"') == '"'
    assert token_to_text("abc") == "abc"


def test_token_to_text_utf8_pair() -> None:
    assert token_to_text("Ã©") == "é"


def test_token_to_text_rejects_partial_utf8() -> None:
    assert token_to_text("Ã") is None


def test_vocab_loads_and_decodes(tmp_path: Path) -> None:
    path = tmp_path / "vocab.json"
    path.write_text(json.dumps({"!": 0, "Ġa": 1, "Ã": 2}), encoding="utf-8")
    vocab = Vocab(path)
    assert vocab.size == 3
    assert vocab.tokens() == [(0, "!"), (1, " a")]
    assert vocab.quote_id() is None


def test_vocab_finds_quote(tmp_path: Path) -> None:
    path = tmp_path / "vocab.json"
    path.write_text(json.dumps({'"': 7, "a": 8}), encoding="utf-8")
    vocab = Vocab(path)
    assert vocab.quote_id() == 7
