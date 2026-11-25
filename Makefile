MAP ?= maps/easy_1.map

POETRY_OK != command -v poetry >/dev/null 2>&1 \
	&& poetry --version >/dev/null 2>&1 && echo yes || echo no

ifeq ($(POETRY_OK),yes)
RUNNER = poetry run
PY = poetry run python3
INSTALL_CMD = poetry install
else
RUNNER =
PY = python3
INSTALL_CMD = python3 -m pip install -r requirements.txt
endif

.PHONY: all install pip-install run gui debug clean lint lint-strict test

all: run

install:
	$(INSTALL_CMD)

pip-install:
	python3 -m pip install -r requirements.txt

run:
	$(PY) main.py $(MAP)

gui:
	$(PY) main.py $(MAP) --gui

debug:
	$(PY) -m pdb main.py $(MAP)

lint:
	$(RUNNER) flake8 .
	$(RUNNER) mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports \
		--disallow-untyped-defs --check-untyped-defs

lint-strict:
	$(RUNNER) flake8 .
	$(RUNNER) mypy . --strict

test:
	$(RUNNER) pytest tests/ -q

clean:
	rm -rf __pycache__ .mypy_cache .pytest_cache tests/__pycache__ .venv dist
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
