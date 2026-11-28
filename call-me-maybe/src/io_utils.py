"""Loading and saving helpers with graceful, explicit error handling.

All file access goes through this module so malformed JSON, missing
files or unwritable paths surface as a single :class:`ProjectError`
with a clear message instead of an unhandled traceback.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.models import FunctionSpec, PromptRequest


class ProjectError(Exception):
    """A user-facing configuration or input error, never a crash."""


def _read_json_array(path: Path, what: str) -> list[Any]:
    """Read a JSON array from ``path`` with explicit error messages."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ProjectError(f"{what} file not found: {path}") from exc
    except IsADirectoryError as exc:
        raise ProjectError(f"{what} path is a directory: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProjectError(f"{what} file is not valid JSON ({path}): {exc}") from exc
    except OSError as exc:
        raise ProjectError(f"{what} file cannot be read ({path}): {exc}") from exc
    if not isinstance(data, list):
        raise ProjectError(f"{what} file must contain a JSON array: {path}")
    return data


def load_functions(path: Path) -> list[FunctionSpec]:
    """Load and validate the function definitions file."""
    data = _read_json_array(path, "functions definition")
    try:
        functions = [FunctionSpec.model_validate(item) for item in data]
    except ValidationError as exc:
        raise ProjectError(f"invalid function definition in {path}: {exc}") from exc
    seen: set[str] = set()
    for function in functions:
        if function.name in seen:
            raise ProjectError(f"duplicate function name {function.name!r} in {path}")
        seen.add(function.name)
    if not functions:
        raise ProjectError(f"no function defined in {path}")
    return functions


def load_prompts(path: Path) -> list[PromptRequest]:
    """Load and validate the prompts file."""
    data = _read_json_array(path, "prompts")
    try:
        return [PromptRequest.model_validate(item) for item in data]
    except ValidationError as exc:
        raise ProjectError(f"invalid prompt entry in {path}: {exc}") from exc


def save_results(results: list[dict[str, Any]], path: Path) -> None:
    """Write the results as pretty-printed JSON, creating directories."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(results, handle, indent=4, ensure_ascii=False)
            handle.write("\n")
    except OSError as exc:
        raise ProjectError(f"cannot write output file {path}: {exc}") from exc


def warn(message: str) -> None:
    """Print a warning on stderr without interrupting the run."""
    print(f"warning: {message}", file=sys.stderr)
