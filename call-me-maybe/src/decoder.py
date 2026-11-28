"""Constrained decoding engine.

The model never decides the structure of the answer: the decoder owns a
state machine that knows exactly which text fragments keep the output a
schema-valid function call. Only where a genuine decision exists (which
function, argument values) are the model logits consulted, and every token
that would break the JSON structure or the schema is masked out by never
being a candidate. The result is 100% parseable JSON by construction.
"""
from __future__ import annotations

from typing import Any, Protocol

from src.models import FunctionSpec, ParameterSpec
from src.vocab import Vocab

MAX_NUMBER_LENGTH = 40
MAX_STRING_LENGTH = 200
NEGATIVE_INFINITY = float("-inf")

INTEGER_TYPES = frozenset({"integer", "int"})
FLOAT_TYPES = frozenset({"number", "float"})
BOOLEAN_TYPES = frozenset({"boolean", "bool"})

QUOTE = '"'


class LLMModel(Protocol):
    """Public surface of the provided ``llm_sdk.Small_LLM_Model``."""

    def encode(self, text: str) -> Any:
        """Encode text into model token ids."""
        ...

    def get_logits_from_input_ids(self, input_ids: list[int]) -> list[float]:
        """Return next-token logits for a sequence of token ids."""
        ...

    def get_path_to_vocab_file(self) -> str:
        """Return the path of the vocabulary file."""
        ...


class DecodingError(Exception):
    """Raised when constrained decoding cannot complete a fragment."""


def _is_number_text(text: str) -> bool:
    """Return True for tokens made only of characters a JSON number uses."""
    if not text:
        return False
    return all(character in "0123456789.-" for character in text)


def _is_string_text(text: str) -> bool:
    """Return True for tokens that can appear inside a plain JSON string."""
    if not text:
        return False
    if QUOTE in text or "\\" in text:
        return False
    return all(ord(character) >= 32 for character in text)


def _number_allowed_characters(current: str, integer_only: bool) -> str:
    """Return characters allowed to continue the number ``current``."""
    if current == "":
        return "0123456789-"
    if current == "-":
        return "0123456789"
    if current.endswith("."):
        return "0123456789"
    if current in ("0", "-0"):
        return "" if integer_only else "."
    return "0123456789" if integer_only else "0123456789."


def _number_can_extend(current: str, addition: str, integer_only: bool) -> bool:
    """Return True if ``addition`` keeps ``current`` a valid number prefix."""
    state = current
    for character in addition:
        if character not in _number_allowed_characters(state, integer_only):
            return False
        state += character
    return True


def _is_complete_number(current: str) -> bool:
    """Return True if ``current`` is already a valid JSON number.

    The state machine only ever produces canonical shapes (no leading
    zeros, no stray dots), so a non-empty value that neither ends with
    "-" nor "." is complete.
    """
    return bool(current) and current != "-" and not current.endswith(".")


def _finalize_number(raw: str) -> str:
    """Drop a stray trailing dot so the value always parses."""
    raw = raw.rstrip(".")
    if raw in ("", "-"):
        return ""
    return raw


class ConstrainedDecoder:
    """Generate schema-valid function calls token-by-token."""

    def __init__(self, model: LLMModel, vocab: Vocab, cache_size: int = 64) -> None:
        """Prepare the decoder from an SDK model and its vocabulary."""
        self._model = model
        self._vocab = vocab
        self._cache_size = cache_size
        self._cache: dict[tuple[int, ...], list[float]] = {}
        self._all_tokens: list[tuple[int, str]] = vocab.tokens()
        self._number_tokens = [
            pair for pair in self._all_tokens if _is_number_text(pair[1])
        ]
        self._string_tokens = [
            pair for pair in self._all_tokens if _is_string_text(pair[1])
        ]
        self._quote_id = vocab.quote_id()
        self._string_candidates = list(self._string_tokens)
        if self._quote_id is not None:
            self._string_candidates.append((self._quote_id, QUOTE))

    def _encode(self, text: str) -> list[int]:
        """Encode ``text`` into a flat list of token ids."""
        tensor = self._model.encode(text)
        return [int(value) for value in tensor[0].tolist()]

    def _logits(self, input_ids: list[int]) -> list[float]:
        """Return logits for ``input_ids``, memoising identical prefixes."""
        key = tuple(input_ids)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        logits = self._model.get_logits_from_input_ids(list(key))
        if len(self._cache) >= self._cache_size:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = logits
        return logits

    def _best_token(
        self,
        input_ids: list[int],
        candidates: list[tuple[int, str]],
        allowed_texts: set[str],
    ) -> tuple[int, str] | None:
        """Return the highest-logit candidate whose text is allowed."""
        if len(allowed_texts) == 1:
            only_text = next(iter(allowed_texts))
            for token_id, text in candidates:
                if text == only_text:
                    return token_id, text
            return None
        logits = self._logits(input_ids)
        best: tuple[int, str] | None = None
        best_score = NEGATIVE_INFINITY
        for token_id, text in candidates:
            if text in allowed_texts and logits[token_id] > best_score:
                best_score = logits[token_id]
                best = (token_id, text)
        return best

    def _decode_literal(
        self, base_text: str, literals: list[str], candidates: list[tuple[int, str]]
    ) -> str:
        """Decode one of ``literals`` token-by-token from ``base_text``.

        The model picks between candidate continuations at every step;
        when several literals share a prefix the choice is deferred until
        the logits disambiguate them.
        """
        current = ""
        for _ in range(MAX_STRING_LENGTH):
            if current in literals:
                return current
            suffixes = [
                literal[len(current):]
                for literal in literals
                if literal.startswith(current) and literal != current
            ]
            allowed = {
                text
                for _, text in candidates
                if any(suffix.startswith(text) for suffix in suffixes)
            }
            if not allowed:
                raise DecodingError(f"no valid continuation for {current!r}")
            if len(allowed) == 1:
                current += next(iter(allowed))
                continue
            chosen = self._best_token(
                self._encode(base_text + current), candidates, allowed
            )
            if chosen is None:
                raise DecodingError(f"no token selected after {current!r}")
            current += chosen[1]
        raise DecodingError("literal did not terminate")

    def _decode_number(self, base_text: str, integer_only: bool) -> str:
        """Decode a JSON number, ending when the model stops preferring digits.

        At each step the candidates are the number-continuation tokens; the
        number terminates as soon as the unconstrained best token scores
        higher than every continuation, meaning the model itself wants to
        move on to the next JSON fragment.
        """
        current = ""
        while len(current) < MAX_NUMBER_LENGTH:
            allowed = {
                text
                for _, text in self._number_tokens
                if _number_can_extend(current, text, integer_only)
            }
            if not allowed:
                break
            input_ids = self._encode(base_text + current)
            logits = self._logits(input_ids)
            best_continuation = self._best_token(input_ids, self._number_tokens, allowed)
            if best_continuation is None:
                break
            global_best = max(range(len(logits)), key=logits.__getitem__)
            if logits[global_best] > logits[best_continuation[0]]:
                break
            current += best_continuation[1]
        return current

    def _decode_string(self, question: str, key: str) -> str:
        """Decode a string argument value with a dedicated echo prompt.

        Raw completion at ``...{"name": "`` tends to ramble with small
        models, so string values are extracted from a focused prompt that
        ends right before the value. Content tokens are constrained to
        complete, escape-free UTF-8 fragments without quotes or control
        characters. The value ends when the model prefers the closing
        quote, or when its unconstrained best token is neither content
        nor the quote (it wants out of the string), or at the length cap.
        """
        base_text = f"Question: {question}\n{key}: " + QUOTE
        current = ""
        while len(current) < MAX_STRING_LENGTH:
            allowed = {
                text
                for _, text in self._string_tokens
                if len(current) + len(text) <= MAX_STRING_LENGTH
            }
            if current:
                allowed.add(QUOTE)
            else:
                allowed = {text for text in allowed if not text[0].isspace()}
            input_ids = self._encode(base_text + current)
            logits = self._logits(input_ids)
            chosen = self._best_token(input_ids, self._string_candidates, allowed)
            if chosen is None:
                break
            if chosen[1] == QUOTE:
                return current
            if current:
                global_best = max(range(len(logits)), key=logits.__getitem__)
                global_is_content = any(
                    token_id == global_best for token_id, _ in self._string_tokens
                )
                if not global_is_content and global_best != self._quote_id:
                    break
            current += chosen[1]
        return current

    def _decode_value(
        self, text: str, spec: ParameterSpec, key: str, question: str
    ) -> tuple[str, Any]:
        """Decode one argument value, returning appended text and value."""
        if spec.type in INTEGER_TYPES:
            raw = _finalize_number(self._decode_number(text, integer_only=True))
            return raw, int(raw) if raw else 0
        if spec.type in FLOAT_TYPES:
            raw = _finalize_number(self._decode_number(text, integer_only=False))
            if "." in raw:
                return raw, float(raw)
            return raw, int(raw) if raw else 0
        if spec.type == "string":
            raw = self._decode_string(question, key)
            return QUOTE + raw + QUOTE, raw
        if spec.type in BOOLEAN_TYPES:
            raw = self._decode_literal(text, ["true", "false"], self._all_tokens)
            return raw, raw == "true"
        if spec.type == "null":
            return "null", None
        raise DecodingError(f"unsupported parameter type {spec.type!r}")

    def _decode_name(self, text: str, functions: list[FunctionSpec]) -> str:
        """Decode the function name from the model logits, quote included."""
        literals = [function.name + QUOTE for function in functions]
        decoded = self._decode_literal(text, literals, self._all_tokens)
        return decoded[:-1]

    def generate_call(
        self, question: str, functions: list[FunctionSpec]
    ) -> tuple[str, dict[str, Any]]:
        """Generate one function call for ``question``.

        Returns the complete JSON object as text (schema-valid by
        construction) together with the tracked parameters, so callers
        never depend on re-parsing the text.
        """
        prompt = build_prompt(question, functions)
        text = prompt
        fragments: list[str] = []
        name = self._decode_name(text, functions)
        text += name + QUOTE
        fragments.append(name + QUOTE)
        parameters: dict[str, Any] = {}
        separator = ", " + QUOTE + "parameters" + QUOTE + ": {"
        text += separator
        fragments.append(separator)
        spec_by_name = {function.name: function for function in functions}
        entries = list(spec_by_name[name].parameters.items())
        for index, (key, spec) in enumerate(entries):
            if index > 0:
                text += ", "
                fragments.append(", ")
            key_fragment = QUOTE + key + QUOTE + ": "
            text += key_fragment
            fragments.append(key_fragment)
            appended, value = self._decode_value(text, spec, key, question)
            text += appended
            fragments.append(appended)
            parameters[key] = value
        fragments.append("}}")
        return '{"name": "' + "".join(fragments), parameters


def build_prompt(question: str, functions: list[FunctionSpec]) -> str:
    """Build the plain-completion prompt the decoder constrains from."""
    lines = ["Available functions:"]
    for function in functions:
        parameters = ", ".join(
            f"{key}: {spec.type}" for key, spec in function.parameters.items()
        )
        lines.append(f"- {function.name}({parameters}): {function.description}")
    lines.append(f"Question: {question}")
    lines.append('Function call: {"name": "')
    return "\n".join(lines)
