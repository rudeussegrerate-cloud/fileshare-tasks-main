"""High level planner: diversify routes, assign drones, then simulate."""

from __future__ import annotations

from instance import Instance
from pathfinding import PathOption, PathPlanner


class PathAssigner:
    """Assign drones to paths balancing predicted completion time.

    The completion estimate of a path carrying k drones is
    `cost` plus `ceil(k / lanes)` (computed with integers): drones
    sharing a route must be spaced out by the path bottleneck capacity.
    """

    def __init__(self, instance: Instance) -> None:
        self.instance = instance
        self.planner = PathPlanner(
            instance.network, instance.start, instance.end
        )

    def assign(
        self, paths: list[PathOption] | None = None
    ) -> list[int]:
        """Return the path index chosen for each drone (per drone id)."""
        if paths is None:
            paths = self.planner.compute_paths()
        nb_drones = self.instance.nb_drones
        assignment: list[int] = []
        loads = [0 for _ in paths]
        for _ in range(nb_drones):
            best_index = 0
            best_estimate: int | None = None
            for index, path in enumerate(paths):
                candidate_load = loads[index] + 1
                estimate = self._makespan(
                    paths, loads, index, candidate_load
                )
                if best_estimate is None or estimate < best_estimate or (
                    estimate == best_estimate
                    and loads[index] < loads[best_index]
                ):
                    best_estimate = estimate
                    best_index = index
            loads[best_index] += 1
            assignment.append(best_index)
        return assignment

    @staticmethod
    def _makespan(
        paths: list[PathOption],
        loads: list[int],
        changed: int,
        new_load: int,
    ) -> int:
        """Return the predicted makespan if drone had joined `changed`.

        The makespan estimate is the maximum, over used paths, of the
        completion time of their most delayed drone.
        """
        estimate = 0
        for index, path in enumerate(paths):
            load = new_load if index == changed else loads[index]
            if load == 0:
                continue
            completion = path.cost + PathAssigner.ceil_div(
                load, path.lanes
            ) - 1
            estimate = max(estimate, completion)
        return estimate

    @staticmethod
    def ceil_div(value: int, divisor: int) -> int:
        """Hand made ceil of an integer division (no math import)."""
        if divisor <= 0:
            return value
        return (value + divisor - 1) // divisor
