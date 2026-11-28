"""Unit tests for input/output helpers and their error handling."""
import json
from pathlib import Path

import pytest

from src.io_utils import ProjectError, load_functions, load_prompts, save_results


def test_load_functions_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ProjectError, match="not found"):
        load_functions(tmp_path / "missing.json")


def test_load_functions_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "functions.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(ProjectError, match="not valid JSON"):
        load_functions(path)


def test_load_functions_rejects_non_array(tmp_path: Path) -> None:
    path = tmp_path / "functions.json"
    path.write_text(json.dumps({"name": "fn_a"}), encoding="utf-8")
    with pytest.raises(ProjectError, match="JSON array"):
        load_functions(path)


def test_load_functions_rejects_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "functions.json"
    path.write_text(
        json.dumps([{"name": "fn_a"}, {"name": "fn_a"}]), encoding="utf-8"
    )
    with pytest.raises(ProjectError, match="duplicate"):
        load_functions(path)


def test_load_functions_rejects_unknown_type(tmp_path: Path) -> None:
    path = tmp_path / "functions.json"
    path.write_text(
        json.dumps(
            [{"name": "fn_a", "parameters": {"x": {"type": "list"}}}]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProjectError, match="unsupported parameter type"):
        load_functions(path)


def test_load_functions_valid(tmp_path: Path) -> None:
    path = tmp_path / "functions.json"
    path.write_text(
        json.dumps(
            [
                {
                    "name": "fn_a",
                    "description": "Does a.",
                    "parameters": {"x": {"type": "number"}},
                    "returns": {"type": "number"},
                }
            ]
        ),
        encoding="utf-8",
    )
    functions = load_functions(path)
    assert len(functions) == 1
    assert functions[0].name == "fn_a"
    assert functions[0].parameters["x"].type == "number"


def test_load_prompts_ignores_extra_keys(tmp_path: Path) -> None:
    path = tmp_path / "prompts.json"
    path.write_text(
        json.dumps([{"prompt": "a"}, {"prompt": "b", "extra": 1}]),
        encoding="utf-8",
    )
    prompts = load_prompts(path)
    assert [request.prompt for request in prompts] == ["a", "b"]


def test_load_prompts_rejects_missing_prompt(tmp_path: Path) -> None:
    path = tmp_path / "prompts.json"
    path.write_text(json.dumps([{}]), encoding="utf-8")
    with pytest.raises(ProjectError, match="invalid prompt entry"):
        load_prompts(path)


def test_save_results_creates_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "out.json"
    save_results([{"prompt": "a", "name": "fn_a", "parameters": {}}], path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == [{"prompt": "a", "name": "fn_a", "parameters": {}}]
