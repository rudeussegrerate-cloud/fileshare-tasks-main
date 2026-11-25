MAP ?= maps/easy_1.map

.PHONY: all install run debug clean lint lint-strict test

all: run

install:
	python3 -m pip install -r requirements.txt

run:
	python3 main.py $(MAP)

debug:
	python3 -m pdb main.py $(MAP)

lint:
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports \
		--disallow-untyped-defs --check-untyped-defs

lint-strict:
	flake8 .
	mypy . --strict

test:
	python3 -m pytest tests/ -q

clean:
	rm -rf __pycache__ .mypy_cache .pytest_cache tests/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} +
