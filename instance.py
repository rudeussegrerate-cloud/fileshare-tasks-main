"""Instance model: a fully parsed Fly-in problem."""

from __future__ import annotations

from errors import ParseError, SimulationError
from network import Network
from zone import Zone


class Instance:
    """A parsed input file: drone count and network with start/end hubs.

    Attributes:
        nb_drones: number of drones to route.
        network: the parsed zone/connection graph.
        start: name of the (unique) start hub.
        end: name of the (unique) end hub.
    """

    def __init__(
        self,
        nb_drones: int,
        network: Network,
        start: str,
        end: str,
    ) -> None:
        self.nb_drones = nb_drones
        self.network = network
        self.start = start
        self.end = end

    @property
    def start_zone(self) -> Zone:
        """Return the start hub zone."""
        return self.network.get_zone(self.start)

    @property
    def end_zone(self) -> Zone:
        """Return the end hub zone."""
        return self.network.get_zone(self.end)

    def validate_topology(self) -> None:
        """Check the parsed problem is routable at all.

        Raises:
            SimulationError: when a start/end path cannot exist.
        """
        if self.start not in self.network.zones:
            raise ParseError("start hub is missing")
        if self.end not in self.network.zones:
            raise ParseError("end hub is missing")
        if not self._reachable(self.start, self.end):
            raise SimulationError(
                f"no valid path from '{self.start}' to '{self.end}' "
                "avoiding blocked zones"
            )

    def _reachable(self, source: str, target: str) -> bool:
        """Breadth-first reachability check between two zones."""
        if source == target:
            return True
        seen: set[str] = {source}
        frontier: list[str] = [source]
        while frontier:
            current = frontier.pop()
            if self.network.get_zone(current).zone_type.enterable is False:
                continue
            for connection in self.network.neighbours(current):
                neighbour = connection.other(current)
                if neighbour == target:
                    return True
                if neighbour not in seen and self.network.get_zone(
                    neighbour
                ).enterable:
                    seen.add(neighbour)
                    frontier.append(neighbour)
        return False
