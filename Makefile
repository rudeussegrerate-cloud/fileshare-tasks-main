MAP ?= maps/easy_1.map
RUN = poetry run python3

.PHONY: all install run gui debug clean lint lint-strict test pip-install

all: run

install:
	poetry install

pip-install:
	python3 -m pip install -r requirements.txt

run:
	$(RUN) main.py $(MAP)

gui:
	$(RUN) main.py $(MAP) --gui

debug:
	$(RUN) -m pdb main.py $(MAP)

lint:
	poetry run flake8 .
	poetry run mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports \
		--disallow-untyped-defs --check-untyped-defs

lint-strict:
	poetry run flake8 .
	poetry run mypy . --strict

test:
	poetry run pytest tests/ -q

clean:
	rm -rf __pycache__ .mypy_cache .pytest_cache tests/__pycache__ .venv dist
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
