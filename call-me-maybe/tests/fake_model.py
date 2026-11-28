"""Fake LLM implementing the public llm_sdk surface for tests.

The fake encodes with greedy longest-match over a tiny vocabulary and
follows a script: the n-th call to ``get_logits_from_input_ids`` gives
logit 1.0 to the token whose text is ``script[n]`` (and 0.0 to the
others), so tests can steer constrained decoding deterministically.
"""
from src.vocab import Vocab

FAKE_VOCAB: dict[str, int] = {
    '"': 0,
    ",": 1,
    "{": 2,
    "}": 3,
    ":": 4,
    " ": 5,
    "a": 6,
    "b": 7,
    "h": 8,
    "i": 9,
    "\n": 10,
    "0": 11,
    "2": 12,
    "4": 13,
    "5": 14,
    ".": 15,
    "-": 16,
    "tr": 17,
    "ue": 18,
    "true": 19,
    "false": 20,
    "sh": 21,
    "rek": 22,
    "fn_a": 23,
    "fn_b": 24,
}


class FakeTensor:
    """Minimal stand-in for the tensor returned by the SDK ``encode``."""

    def __init__(self, ids: list[int]) -> None:
        self._ids = ids

    def tolist(self) -> list[int]:
        return list(self._ids)

    def __getitem__(self, index: int) -> "FakeTensor":
        return FakeTensor(self._ids)


class FakeModel:
    """Deterministic scripted model for decoder tests."""

    def __init__(self, vocab: Vocab, script: list[str]) -> None:
        self._vocab = vocab
        self._script = script
        self._calls = 0

    def encode(self, text: str) -> FakeTensor:
        ids: list[int] = []
        position = 0
        tokens_by_length = sorted(
            FAKE_VOCAB.items(), key=lambda item: len(item[0]), reverse=True
        )
        while position < len(text):
            for token, token_id in tokens_by_length:
                if token and text.startswith(token, position):
                    ids.append(token_id)
                    position += len(token)
                    break
            else:
                position += 1
        return FakeTensor(ids)

    def get_logits_from_input_ids(self, input_ids: list[int]) -> list[float]:
        preferred = self._script[self._calls] if self._calls < len(self._script) else ""
        self._calls += 1
        logits = [0.0] * (max(FAKE_VOCAB.values()) + 1)
        if preferred in FAKE_VOCAB:
            logits[FAKE_VOCAB[preferred]] = 1.0
        return logits

    def get_path_to_vocab_file(self) -> str:
        return self._vocab.path
