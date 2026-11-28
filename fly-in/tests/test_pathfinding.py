"""Pathfinding tests."""

from __future__ import annotations

from parser import Parser
from instance import Instance
from pathfinding import PathPlanner, ShortestPathFinder
from zone import ZoneType

from sample_maps import LINEAR_MAP


def build(content: str) -> tuple[Instance, ShortestPathFinder]:
    """Parse content and return (instance, finder)."""
    instance = Parser().parse(content)
    instance.validate_topology()
    return instance, ShortestPathFinder(instance.network)


def test_shortest_follows_the_line() -> None:
    instance, finder = build(LINEAR_MAP)
    path = finder.shortest_path(instance.start, instance.end)
    assert path == ["start", "a", "b", "end"]


def test_restricted_zone_costs_two_turns() -> None:
    from sample_maps import RESTRICTED_MAP

    instance, finder = build(RESTRICTED_MAP)
    path = finder.shortest_path(instance.start, instance.end)
    assert path == ["start", "lab", "b", "end"]
    planner = PathPlanner(instance.network, instance.start, instance.end)
    option = planner.compute_paths(limit=1)[0]
    assert option.cost == 4


def test_blocked_zones_are_avoided() -> None:
    content = """
nb_drones: 1
start_hub: start 0 0
end_hub: end 4 0
hub: trap 1 0 [zone=blocked]
hub: detour 1 2
hub: gate 2 2
hub: gate2 3 2
hub: gate3 4 2
connection: start-trap
connection: trap-end
connection: start-detour
connection: detour-gate
connection: gate-gate2
connection: gate2-gate3
connection: gate3-end
"""
    instance, finder = build(content)
    path = finder.shortest_path(instance.start, instance.end)
    assert path is not None
    for zone in path:
        assert instance.network.get_zone(zone).zone_type is not (
            ZoneType.BLOCKED
        )


def test_priority_zone_preferred_on_ties() -> None:
    content = """
nb_drones: 1
start_hub: start 0 1
end_hub: end 4 1
hub: p1 1 1 [zone=priority]
hub: p2 2 1 [zone=priority]
hub: p3 3 1 [zone=priority]
hub: n1 1 3
hub: n2 2 3
hub: n3 3 3
connection: start-p1
connection: p1-p2
connection: p2-p3
connection: p3-end
connection: start-n1
connection: n1-n2
connection: n2-n3
connection: n3-end
"""
    instance, finder = build(content)
    path = finder.shortest_path(instance.start, instance.end)
    assert path == ["start", "p1", "p2", "p3", "end"]


def test_unreachable_end() -> None:
    import pytest

    from errors import SimulationError

    content = """
nb_drones: 1
start_hub: start 0 0
end_hub: end 4 0
hub: a 1 0
connection: start-a
"""
    instance = Parser().parse(content)
    with pytest.raises(SimulationError):
        instance.validate_topology()


def test_diverse_paths_are_produced() -> None:
    from sample_maps import PARALLEL_MAP

    instance = Parser().parse(PARALLEL_MAP)
    planner = PathPlanner(instance.network, instance.start, instance.end)
    paths = planner.compute_paths()
    distinct = {tuple(path.zones) for path in paths}
    assert len(distinct) == len(paths) == 2
