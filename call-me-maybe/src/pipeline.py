"""End-to-end pipeline: turn prompts into validated function calls."""
from __future__ import annotations

import json
from typing import Any

from src.decoder import ConstrainedDecoder, DecodingError
from src.io_utils import warn
from src.models import FunctionCall, FunctionSpec, ParameterSpec, PromptRequest

_DEFAULT_VALUES: dict[str, Any] = {
    "number": 0,
    "float": 0,
    "integer": 0,
    "int": 0,
    "string": "",
    "boolean": False,
    "bool": False,
    "null": None,
}


def _default_value(spec: ParameterSpec) -> Any:
    """Return a schema-compliant placeholder for a failed generation."""
    return _DEFAULT_VALUES[spec.type]


def fallback_call(prompt: str, functions: list[FunctionSpec]) -> FunctionCall:
    """Build a schema-compliant call when constrained decoding failed."""
    function = functions[0]
    parameters = {
        key: _default_value(spec) for key, spec in function.parameters.items()
    }
    return FunctionCall(prompt=prompt, name=function.name, parameters=parameters)


def _validate_parameters(
    function: FunctionSpec, parameters: dict[str, Any]
) -> None:
    """Check generated parameters against the function definition."""
    expected = set(function.parameters)
    if set(parameters) != expected:
        raise DecodingError(
            f"parameters {sorted(parameters)} do not match {sorted(expected)}"
        )
    for key, spec in function.parameters.items():
        value = parameters[key]
        valid = (
            (spec.type in ("number", "float") and isinstance(value, (int, float)))
            or (spec.type in ("integer", "int") and isinstance(value, int))
            or (spec.type == "string" and isinstance(value, str))
            or (spec.type in ("boolean", "bool") and isinstance(value, bool))
            or (spec.type == "null" and value is None)
        )
        if not valid:
            raise DecodingError(
                f"argument {key!r} value {value!r} does not match type {spec.type!r}"
            )


def process_prompt(
    decoder: ConstrainedDecoder,
    request: PromptRequest,
    functions: list[FunctionSpec],
) -> FunctionCall:
    """Produce one function call, never raising for a single prompt."""
    try:
        generated, parameters = decoder.generate_call(request.prompt, functions)
        parsed: dict[str, Any] = json.loads(generated)
        if set(parsed) != {"name", "parameters"}:
            raise DecodingError(f"unexpected keys in generated object: {sorted(parsed)}")
        function_by_name = {function.name: function for function in functions}
        if parsed["name"] not in function_by_name:
            raise DecodingError(f"unknown function name {parsed['name']!r}")
        _validate_parameters(function_by_name[parsed["name"]], parameters)
        if parsed["parameters"] != parameters:
            raise DecodingError("generated text and tracked parameters diverge")
        return FunctionCall(
            prompt=request.prompt, name=parsed["name"], parameters=parameters
        )
    except Exception as exc:  # noqa: BLE001 - a prompt must never crash the run
        warn(f"constrained decoding failed for prompt {request.prompt!r}: {exc}")
        return fallback_call(request.prompt, functions)


def run_pipeline(
    decoder: ConstrainedDecoder,
    prompts: list[PromptRequest],
    functions: list[FunctionSpec],
) -> list[FunctionCall]:
    """Run every prompt through the constrained decoder in order."""
    return [process_prompt(decoder, request, functions) for request in prompts]
