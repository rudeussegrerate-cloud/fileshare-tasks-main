"""Simulation engine and validator tests."""

from __future__ import annotations

from parser import Parser
from validator import SimulationValidator

from conftest import solve_map
from sample_maps import LINEAR_MAP, PARALLEL_MAP, RESTRICTED_MAP


def test_output_format_matches_subject() -> None:
    result = solve_map("easy_1.map")
    for moves in result.turns:
        for token in moves:
            assert token.startswith("D")
            assert "-" in token


def test_linear_map_within_target() -> None:
    result = solve_map("easy_1.map")
    assert result.total_turns <= 6
    assert len(result.arrival_turns) == 2


def test_simple_fork_within_target() -> None:
    result = solve_map("easy_2.map")
    assert result.total_turns <= 8
    assert len(result.arrival_turns) == 4


def test_basic_capacity_within_target() -> None:
    result = solve_map("easy_3.map")
    assert result.total_turns <= 6
    assert len(result.arrival_turns) == 4


def test_dead_end_trap_within_target() -> None:
    result = solve_map("medium_1.map")
    assert result.total_turns <= 12


def test_circular_loop_within_target() -> None:
    result = solve_map("medium_2.map")
    assert result.total_turns <= 15


def test_priority_puzzle_within_target() -> None:
    result = solve_map("medium_3.map")
    assert result.total_turns <= 12


def test_maze_nightmare_within_target() -> None:
    result = solve_map("hard_1.map")
    assert result.total_turns <= 30


def test_capacity_hell_within_target() -> None:
    result = solve_map("hard_2.map")
    assert result.total_turns <= 35


def test_ultimate_challenge_within_target() -> None:
    result = solve_map("hard_3.map")
    assert result.total_turns <= 45


def test_challenger_map_beats_reference_record() -> None:
    result = solve_map("challenger.map")
    assert result.total_turns < 45


def test_restricted_transit_output() -> None:
    instance = Parser().parse(RESTRICTED_MAP)
    instance.validate_topology()
    from simulation import Simulator

    result = Simulator(instance).run()
    report = SimulationValidator(instance).validate(result.turns)
    assert report.ok, report.violations
    assert result.turns[0] == ["D1-start-lab"]
    assert "D1-lab" in result.turns[1]


def test_drones_spread_across_paths() -> None:
    instance = Parser().parse(PARALLEL_MAP)
    instance.validate_topology()
    from simulation import Simulator

    result = Simulator(instance).run()
    report = SimulationValidator(instance).validate(result.turns)
    assert report.ok, report.violations
    first_moves = result.turns[0]
    assert len(first_moves) == 2


def test_validator_rejects_unlinked_move() -> None:
    instance = Parser().parse(LINEAR_MAP)
    report = SimulationValidator(instance).validate([["D1-end"]])
    assert not report.ok


def test_validator_rejects_capacity_overflow() -> None:
    content = PARALLEL_MAP.replace(
        "hub: up 1 0 [max_drones=2]", "hub: up 1 0 [max_drones=1]"
    )
    instance = Parser().parse(content)
    report = SimulationValidator(instance).validate(
        [["D1-up", "D2-up"], ["D1-up2", "D2-up2"]]
    )
    assert not report.ok


def test_validator_rejects_missing_landing() -> None:
    content = RESTRICTED_MAP.rsplit("connection: b-end", 1)[0]
    instance = Parser().parse(content)
    report = SimulationValidator(instance).validate([["D1-start-lab"]])
    assert not report.ok


def test_validator_rejects_incomplete_fleet() -> None:
    instance = Parser().parse(RESTRICTED_MAP)
    report = SimulationValidator(instance).validate([])
    assert not report.ok


def test_validator_rejects_double_move() -> None:
    instance = Parser().parse(LINEAR_MAP)
    report = SimulationValidator(instance).validate([["D1-a", "D1-b"]])
    assert not report.ok
