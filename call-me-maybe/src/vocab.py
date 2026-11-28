"""Token vocabulary utilities.

The subject hints that the vocabulary JSON file is the bridge between token
ids and their string representations. Qwen tokenizers use byte-level BPE:
each vocabulary entry is written in a reversible unicode mapping of the raw
bytes (spaces become the character "Ġ", newlines "Ċ", and so on). This
module reverses that mapping so constrained decoding can reason about the
actual text a token would add to the output.
"""
from __future__ import annotations

import json
from pathlib import Path


def _bytes_to_unicode() -> dict[int, str]:
    """Return the reversible byte-to-unicode table used by byte-level BPE.

    Printable ascii and latin-1 ranges map to themselves; the remaining
    bytes are shifted above 256 so every byte has a distinct printable
    character.
    """
    byte_values: list[int] = list(range(33, 127))
    byte_values += list(range(161, 173))
    byte_values += list(range(174, 256))
    code_points: list[int] = byte_values[:]
    offset = 0
    for byte in range(256):
        if byte not in byte_values:
            byte_values.append(byte)
            code_points.append(256 + offset)
            offset += 1
    return dict(zip(byte_values, (chr(code) for code in code_points)))


_CHAR_TO_BYTE: dict[str, int] = {
    char: byte for byte, char in _bytes_to_unicode().items()
}


def token_to_text(token: str) -> str | None:
    """Convert one vocabulary entry to the text it appends to the output.

    Returns ``None`` when the token contains characters outside the
    byte-level mapping or does not decode to complete UTF-8 (partial
    multi-byte sequences cannot be appended to a string safely).
    """
    raw = bytearray()
    for char in token:
        byte = _CHAR_TO_BYTE.get(char)
        if byte is None:
            return None
        raw.append(byte)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


class Vocab:
    """Read-only view over the model vocabulary: token id to text."""

    def __init__(self, vocab_path: str | Path) -> None:
        """Load and decode the vocabulary file produced by the SDK."""
        self.path: str = str(vocab_path)
        with open(vocab_path, encoding="utf-8") as handle:
            raw: dict[str, int] = json.load(handle)
        self.size: int = len(raw)
        self._id_to_text: dict[int, str] = {}
        for token, token_id in raw.items():
            text = token_to_text(token)
            if text is not None:
                self._id_to_text[token_id] = text

    def tokens(self) -> list[tuple[int, str]]:
        """Return every decodable token as a ``(token_id, text)`` pair."""
        return sorted(self._id_to_text.items())

    def quote_id(self) -> int | None:
        """Return the id of the plain double-quote token, if present."""
        for token_id, text in self._id_to_text.items():
            if text == '"':
                return token_id
        return None
