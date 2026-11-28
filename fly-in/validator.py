"""Independent validation of simulation outputs.

The validator replays the raw move lines against the rules of the
subject: adjacency, zone types, restricted zone transits, zone
capacities, connection capacities and end zone delivery. It is used by
the test suite and by the `--check` option.
"""

from __future__ import annotations

from connection import Connection
from datastructures import Multiset, link_key
from instance import Instance
from network import ConnectionKey


class Flight:
    """A drone currently traversing a connection (2-turn transit).

    Attributes:
        link: canonical key of the traversed connection.
        destination: restricted zone reached at the landing turn.
    """

    def __init__(self, link: ConnectionKey, destination: str) -> None:
        self.link = link
        self.destination = destination


class ValidationReport:
    """Result of a validation pass."""

    def __init__(self) -> None:
        self.violations: list[str] = []

    @property
    def ok(self) -> bool:
        """Return True when no violation was found."""
        return not self.violations

    def add(self, message: str) -> None:
        """Record a violation."""
        self.violations.append(message)


class SimulationValidator:
    """Replays simulation lines and checks every movement rule."""

    def __init__(self, instance: Instance) -> None:
        self.instance = instance
        self.network = instance.network

    def validate(self, turns: list[list[str]]) -> ValidationReport:
        """Replay all turns and return the violation report."""
        report = ValidationReport()
        position: dict[int, str] = {
            drone_id: self.instance.start
            for drone_id in range(1, self.instance.nb_drones + 1)
        }
        flights: dict[int, Flight] = {}
        occupancy = Multiset[str]({self.instance.start: self.instance.nb_drones})
        for turn_no, moves in enumerate(turns, start=1):
            link_use = Multiset[ConnectionKey]()
            seen: set[int] = set()
            for token in moves:
                drone_id, rest = self._split(token, turn_no, report)
                if drone_id is None or rest is None:
                    continue
                if drone_id in seen:
                    report.add(
                        f"turn {turn_no}: '{token}' moves a drone twice"
                    )
                    continue
                seen.add(drone_id)
                if drone_id in flights:
                    flight = flights.pop(drone_id)
                    self._land(
                        drone_id, flight, rest, occupancy, position,
                        turn_no, report,
                    )
                    continue
                if rest in self.network.zones:
                    self._walk(
                        drone_id, position, rest, occupancy, link_use,
                        turn_no, report,
                    )
                else:
                    self._board(
                        drone_id, position, rest, occupancy, flights,
                        link_use, turn_no, report,
                    )
            self._check_links(turn_no, link_use, report)
            self._check_occupancy(turn_no, occupancy, report)
        for drone_id in range(1, self.instance.nb_drones + 1):
            if position.get(drone_id) != self.instance.end:
                report.add(f"drone D{drone_id} never reached the end hub")
            if drone_id in flights:
                report.add(f"drone D{drone_id} never landed")
        return report

    def _split(
        self,
        token: str,
        turn_no: int,
        report: ValidationReport,
    ) -> tuple[int | None, str | None]:
        """Split a 'D1-zone' token into drone id and destination."""
        if not token.startswith("D") or "-" not in token:
            report.add(f"turn {turn_no}: malformed token '{token}'")
            return None, None
        head, _, rest = token.partition("-")
        try:
            drone_id = int(head[1:])
        except ValueError:
            report.add(f"turn {turn_no}: malformed token '{token}'")
            return None, None
        if rest not in self.network.zones and self._by_name(rest) is None:
            report.add(
                f"turn {turn_no}: unknown destination '{rest}' in '{token}'"
            )
            return None, None
        return drone_id, rest

    def _by_name(self, name: str) -> Connection | None:
        """Find a connection by its 'a-b' name, if any."""
        parts = name.split("-")
        if len(parts) != 2:
            return None
        return self.network.connections.get(link_key(parts[0], parts[1]))

    def _walk(
        self,
        drone_id: int,
        position: dict[int, str],
        destination: str,
        occupancy: Multiset[str],
        link_use: Multiset[ConnectionKey],
        turn_no: int,
        report: ValidationReport,
    ) -> None:
        """Check and apply a plain one-turn move onto a zone."""
        source = position[drone_id]
        if not self.network.is_adjacent(source, destination):
            report.add(
                f"turn {turn_no}: D{drone_id} moved from '{source}' "
                f"to unconnected '{destination}'"
            )
            return
        zone = self.network.get_zone(destination)
        if not zone.enterable:
            report.add(
                f"turn {turn_no}: D{drone_id} entered blocked zone "
                f"'{destination}'"
            )
            return
        occupancy.remove(source)
        occupancy.add(destination)
        position[drone_id] = destination
        link_use.add(link_key(source, destination))

    def _board(
        self,
        drone_id: int,
        position: dict[int, str],
        connection_name: str,
        occupancy: Multiset[str],
        flights: dict[int, Flight],
        link_use: Multiset[ConnectionKey],
        turn_no: int,
        report: ValidationReport,
    ) -> None:
        """Check and apply the start of a 2-turn transit."""
        source = position[drone_id]
        connection = self._by_name(connection_name)
        if connection is None or source not in (
            connection.zone_a,
            connection.zone_b,
        ):
            report.add(
                f"turn {turn_no}: D{drone_id} used unknown connection "
                f"'{connection_name}' from '{source}'"
            )
            return
        destination = connection.other(source)
        target = self.network.get_zone(destination)
        if target.zone_type.value != "restricted" or not target.enterable:
            report.add(
                f"turn {turn_no}: D{drone_id} entered connection "
                f"'{connection_name}' towards non restricted zone "
                f"'{destination}'"
            )
            return
        occupancy.remove(source)
        flights[drone_id] = Flight(connection.key(), destination)
        link_use.add(connection.key())

    def _land(
        self,
        drone_id: int,
        flight: Flight,
        destination: str,
        occupancy: Multiset[str],
        position: dict[int, str],
        turn_no: int,
        report: ValidationReport,
    ) -> None:
        """Check and apply the mandatory landing after a transit."""
        if destination != flight.destination:
            report.add(
                f"turn {turn_no}: D{drone_id} landed on '{destination}' "
                f"instead of '{flight.destination}'"
            )
            return
        occupancy.add(destination)
        position[drone_id] = destination

    def _check_occupancy(
        self,
        turn_no: int,
        occupancy: Multiset[str],
        report: ValidationReport,
    ) -> None:
        """Check zone capacities at the end of a turn."""
        for zone_name, count in occupancy.items():
            if zone_name not in self.network.zones or count <= 0:
                continue
            zone = self.network.get_zone(zone_name)
            capacity = zone.capacity
            if capacity is not None and count > capacity:
                report.add(
                    f"turn {turn_no}: zone '{zone_name}' holds {count} "
                    f"drones (max {capacity})"
                )

    def _check_links(
        self,
        turn_no: int,
        link_use: Multiset[ConnectionKey],
        report: ValidationReport,
    ) -> None:
        """Check connection capacities for one turn."""
        for key, usage in link_use.items():
            connection = self.network.connections.get(key)
            if connection is None:
                continue
            if usage > connection.capacity:
                report.add(
                    f"turn {turn_no}: connection '{connection.name}' "
                    f"traversed {usage} times (max {connection.capacity})"
                )
