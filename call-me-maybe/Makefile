.PHONY: install run debug clean lint lint-strict test

# On 42 school machines the home directory is too small for model
# caches and virtual environments: route them to the goinfre volume
# when it exists, keeping the evaluator's uv/huggingface setup working.
GOINFRE := /goinfre/$(USER)
ifneq ($(wildcard $(GOINFRE)/.),)
export UV_CACHE_DIR ?= $(GOINFRE)/uv-cache
export UV_PROJECT_ENVIRONMENT ?= $(GOINFRE)/venvs/call-me-maybe
export HF_HOME ?= $(GOINFRE)/hf-cache
endif

install:
	uv sync

run:
	uv run python -m src

debug:
	uv run python -m pdb -m src

clean:
	rm -rf .mypy_cache .pytest_cache .ruff_cache
	find . -name "__pycache__" -type d -not -path "./.venv/*" -exec rm -rf {} +

lint:
	uv run flake8 . && uv run mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	uv run flake8 . && uv run mypy . --strict

test:
	uv run pytest tests/
