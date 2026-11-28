"""Command line entry point: ``uv run python -m src``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from llm_sdk import Small_LLM_Model

from src.decoder import ConstrainedDecoder
from src.io_utils import ProjectError, load_functions, load_prompts, save_results
from src.pipeline import run_pipeline
from src.vocab import Vocab

DEFAULT_FUNCTIONS = Path("data/input/functions_definition.json")
DEFAULT_INPUT = Path("data/input/function_calling_tests.json")
DEFAULT_OUTPUT = Path("data/output/function_calling_results.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the optional paths documented in the subject."""
    parser = argparse.ArgumentParser(
        prog="src",
        description=(
            "Translate natural-language prompts into function calls using "
            "constrained decoding over a small local LLM."
        ),
    )
    parser.add_argument(
        "--functions_definition",
        type=Path,
        default=DEFAULT_FUNCTIONS,
        help=f"path to the function definitions JSON (default: {DEFAULT_FUNCTIONS})",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"path to the prompts JSON (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"path to the results JSON (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args(argv)


def build_decoder() -> ConstrainedDecoder:
    """Load the LLM and its vocabulary, wrapped for graceful failures."""
    try:
        model = Small_LLM_Model()
        vocab = Vocab(model.get_path_to_vocab_file())
    except Exception as exc:
        raise ProjectError(f"failed to initialise the LLM: {exc}") from exc
    return ConstrainedDecoder(model, vocab)


def main(argv: list[str] | None = None) -> int:
    """Run the full pipeline; returns a process exit code."""
    args = parse_args(argv)
    try:
        functions = load_functions(args.functions_definition)
        prompts = load_prompts(args.input)
        decoder = build_decoder()
    except ProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    results = run_pipeline(decoder, prompts, functions)
    payload = [call.model_dump() for call in results]
    try:
        save_results(payload, args.output)
    except ProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {len(payload)} function call(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
