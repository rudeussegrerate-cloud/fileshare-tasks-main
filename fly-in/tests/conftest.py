"""Shared helpers for the Fly-in test suite."""

from __future__ import annotations

import os

import pytest

from parser import Parser
from simulation import SimulationResult, Simulator
from validator import SimulationValidator

MAPS_DIR = os.path.join(os.path.dirname(__file__), "..", "maps")


def map_path(name: str) -> str:
    """Return the absolute path of a bundled map file."""
    return os.path.join(MAPS_DIR, name)


def solve_map(name: str) -> SimulationResult:
    """Parse, simulate and validate a bundled map file."""
    instance = Parser().parse_file(map_path(name))
    instance.validate_topology()
    result = Simulator(instance).run()
    report = SimulationValidator(instance).validate(result.turns)
    if not report.ok:
        raise AssertionError(report.violations)
    assert result.arrival_turns
    return result


@pytest.fixture(name="parser")
def parser_fixture() -> Parser:
    """A fresh parser instance."""
    return Parser()
