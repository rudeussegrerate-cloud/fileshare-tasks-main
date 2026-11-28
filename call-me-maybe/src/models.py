"""Pydantic models describing function definitions, prompts and results.

Every data structure exchanged by the pipeline is validated with pydantic,
as required by the subject: malformed input files are rejected with clear
error messages instead of crashing later during generation.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_TYPES: tuple[str, ...] = (
    "number",
    "integer",
    "float",
    "int",
    "string",
    "boolean",
    "bool",
    "null",
)


class ParameterSpec(BaseModel):
    """Type specification of one function parameter (or return value)."""

    type: str
    description: str = ""

    @field_validator("type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        """Reject parameter types the constrained decoder cannot enforce."""
        if value not in SUPPORTED_TYPES:
            raise ValueError(
                f"unsupported parameter type {value!r}, "
                f"expected one of {', '.join(SUPPORTED_TYPES)}"
            )
        return value


class FunctionSpec(BaseModel):
    """One callable function as described in functions_definition.json."""

    name: str = Field(min_length=1)
    description: str = ""
    parameters: dict[str, ParameterSpec] = Field(default_factory=dict)
    returns: ParameterSpec | None = None


class PromptRequest(BaseModel):
    """One natural-language prompt from function_calling_tests.json."""

    model_config = ConfigDict(extra="ignore")

    prompt: str


class FunctionCall(BaseModel):
    """Result for one prompt: exactly the keys required by the subject."""

    model_config = ConfigDict(extra="forbid")

    prompt: str
    name: str
    parameters: dict[str, Any]
