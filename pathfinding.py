"""Pathfinding for the Fly-in project (no external graph library).

Implements a Dijkstra search over the zone graph with:
  * movement costs derived from zone types (restricted = 2 turns),
  * a lexicographic tie-break preferring 'priority' zones,
  * support for cost penalties and forbidden links, used by the
    path diversification strategy.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from errors import SimulationError
from network import Network

HeapKey = tuple[int, int, int]


@dataclass
class PenaltyState:
    """Extra costs and forbidden links applied to a search.

    Attributes:
        zone_penalty: extra traversal cost added per visited zone.
        link_penalty: extra cost added per traversed link.
        forbidden_links: links that must not be used at all.
    """

    zone_penalty: dict[str, int] = field(default_factory=dict)
    link_penalty: dict[frozenset[str], int] = field(default_factory=dict)
    forbidden_links: set[frozenset[str]] = field(default_factory=set)


class ShortestPathFinder:
    """Dijkstra based router over the network."""

    def __init__(self, network: Network) -> None:
        self.network = network

    def step_cost(self, source: str, target: str) -> int:
        """Return the turn cost of moving from one zone to another.

        Moving towards a restricted zone costs 2 turns. Blocked zones
        are never entered.
        """
        zone = self.network.get_zone(target)
        if not zone.enterable:
            return 0
        return zone.entry_cost

    def shortest_path(
        self,
        source: str,
        target: str,
        penalties: PenaltyState | None = None,
    ) -> list[str] | None:
        """Return the cheapest zone path, or None when unreachable.

        The search minimizes (total turn cost, number of non priority
        zones visited) so that equally long paths prefer 'priority'
        zones as required by the subject.
        """
        state = penalties if penalties is not None else PenaltyState()
        if source == target:
            return [source]
        if not self.network.get_zone(target).enterable:
            return None
        best: dict[str, HeapKey] = {source: (0, 0, 0)}
        queue: list[tuple[HeapKey, str, int]] = [((0, 0, 0), source, 0)]
        came_from: dict[str, tuple[str, int]] = {}
        hops = 0
        while queue:
            key, current, current_hops = heapq.heappop(queue)
            if key > best.get(current, (0, 0, 0)):
                continue
            if current == target:
                break
            for connection in self.network.neighbours(current):
                neighbour = connection.other(current)
                link_key = connection.key()
                if link_key in state.forbidden_links:
                    continue
                if not self.network.get_zone(neighbour).enterable:
                    continue
                cost = self.step_cost(current, neighbour)
                extra = state.zone_penalty.get(neighbour, 0)
                extra += state.link_penalty.get(link_key, 0)
                priority_flag = 0 if (
                    self.network.get_zone(neighbour).zone_type.value
                    == "priority"
                ) else 1
                next_key: HeapKey = (
                    key[0] + cost + extra,
                    key[1] + priority_flag,
                    current_hops + 1,
                )
                if neighbour in best and next_key >= best[neighbour]:
                    continue
                best[neighbour] = next_key
                came_from[neighbour] = (current, cost)
                heapq.heappush(
                    queue, (next_key, neighbour, current_hops + 1)
                )
            hops += 1
        if target not in came_from:
            return None
        return self._reconstruct(came_from, source, target, hops)

    @staticmethod
    def _reconstruct(
        came_from: dict[str, tuple[str, int]],
        source: str,
        target: str,
        _hops: int,
    ) -> list[str]:
        """Walk the predecessor chain backwards from the target."""
        path: list[str] = [target]
        current = target
        while current != source:
            previous = came_from[current][0]
            path.append(previous)
            current = previous
        path.reverse()
        return path


@dataclass
class PathOption:
    """A candidate route between the start and end hubs.

    Attributes:
        zones: zone names along the path (start and end included).
        cost: total movement cost in turns.
        lanes: maximum number of drones that can flow through the path
            in parallel, capped by zone and link capacities.
    """

    zones: list[str]
    cost: int
    lanes: int

    @property
    def links(self) -> list[frozenset[str]]:
        """Return the frozenset keys of every link on the path."""
        return [
            frozenset((a, b)) for a, b in zip(self.zones, self.zones[1:])
        ]


class PathPlanner:
    """Compute a diverse set of start-to-end routes."""

    MAX_PATHS = 8
    PENALTY = 3

    def __init__(self, network: Network, start: str, end: str) -> None:
        self.network = network
        self.finder = ShortestPathFinder(network)
        self.start = start
        self.end = end

    def compute_paths(self, limit: int = MAX_PATHS) -> list[PathOption]:
        """Return up to `limit` diverse routes via cost penalization.

        After each found path, its zones and links get an extra cost so
        the next search is pushed towards new corridors. Accepted paths
        never use a link in the opposite direction of an already
        accepted path, preventing head-on flow deadlocks.
        """
        penalties = PenaltyState()
        paths: list[PathOption] = []
        seen: set[tuple[str, ...]] = set()
        directed: set[tuple[str, str]] = set()
        while len(paths) < limit:
            path: list[str] | None = None
            for _attempt in range(self.network.zone_count + 1):
                candidate = self.finder.shortest_path(
                    self.start, self.end, penalties
                )
                if candidate is None:
                    break
                conflict = self._opposing_link(candidate, directed)
                if conflict is None:
                    path = candidate
                    break
                penalties.link_penalty[frozenset(conflict)] = (
                    penalties.link_penalty.get(frozenset(conflict), 0)
                    + len(self.network.zones) * self.PENALTY
                )
            if path is None or tuple(path) in seen:
                break
            seen.add(tuple(path))
            paths.append(self._make_option(path))
            self._remember_directions(path, directed)
            self._penalize(path, penalties)
        if not paths:
            raise SimulationError(
                f"no valid path from '{self.start}' to '{self.end}'"
            )
        return paths

    @staticmethod
    def _opposing_link(
        path: list[str], directed: set[tuple[str, str]]
    ) -> tuple[str, str] | None:
        """Return the first link used in the opposite direction."""
        for a, b in zip(path, path[1:]):
            if (b, a) in directed:
                return (a, b)
        return None

    @staticmethod
    def _remember_directions(
        path: list[str], directed: set[tuple[str, str]]
    ) -> None:
        """Record the directed traversal of an accepted path."""
        for a, b in zip(path, path[1:]):
            directed.add((a, b))

    def _make_option(self, path: list[str]) -> PathOption:
        """Compute cost and throughput lanes of a path."""
        cost = 0
        lanes = 0
        for index, zone_name in enumerate(path):
            zone = self.network.get_zone(zone_name)
            if index > 0:
                cost += zone.entry_cost
            if 0 < index < len(path) - 1:
                zone_load = zone.capacity if zone.capacity is not None else (
                    len(self.network.zones) + 1
                )
                lanes = zone_load if lanes == 0 else min(lanes, zone_load)
        for a, b in zip(path, path[1:]):
            link = self.network.get_connection(a, b)
            lane_cap = link.capacity
            lanes = min(lanes, lane_cap) if lanes > 0 else lane_cap
        return PathOption(zones=path, cost=cost, lanes=max(lanes, 1))

    def _penalize(self, path: list[str], penalties: PenaltyState) -> None:
        """Increase costs around an already selected path."""
        for zone_name in path:
            penalties.zone_penalty[zone_name] = (
                penalties.zone_penalty.get(zone_name, 0) + self.PENALTY
            )
        for a, b in zip(path, path[1:]):
            key = frozenset((a, b))
            penalties.link_penalty[key] = (
                penalties.link_penalty.get(key, 0) + self.PENALTY
            )
