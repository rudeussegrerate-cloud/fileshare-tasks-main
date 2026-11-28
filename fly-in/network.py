"""Network graph of the Fly-in project.

Implemented without any external graph library (graph libs are
forbidden by the subject): a plain adjacency structure.
"""

from __future__ import annotations

from connection import Connection
from datastructures import link_key
from errors import ParseError, SimulationError
from zone import Zone

ConnectionKey = tuple[str, str]
"""Canonical undirected key of a connection, normalized by link_key()."""


class Network:
    """A graph of connected zones.

    Attributes:
        zones: mapping of zone name to Zone, in definition order.
        connections: mapping of connection key to Connection.
    """

    def __init__(self) -> None:
        self.zones: dict[str, Zone] = {}
        self.connections: dict[ConnectionKey, Connection] = {}

    def add_zone(self, zone: Zone, line_no: int | None = None) -> None:
        """Register a zone, rejecting duplicate names."""
        if zone.name in self.zones:
            raise ParseError(f"duplicate zone name '{zone.name}'", line_no)
        self.zones[zone.name] = zone

    def add_connection(
        self,
        connection: Connection,
        line_no: int | None = None,
    ) -> None:
        """Register a connection between already defined zones."""
        for zone_name in (connection.zone_a, connection.zone_b):
            if zone_name not in self.zones:
                raise ParseError(
                    f"connection references undefined zone '{zone_name}'",
                    line_no,
                )
        if connection.zone_a == connection.zone_b:
            raise ParseError(
                "connection must link two distinct zones", line_no
            )
        key = connection.key()
        if key in self.connections:
            existing = self.connections[key]
            raise ParseError(
                f"duplicate connection '{existing.name}'", line_no
            )
        self.connections[key] = connection

    def get_zone(self, name: str) -> Zone:
        """Return the zone with the given name."""
        zone = self.zones.get(name)
        if zone is None:
            raise SimulationError(f"unknown zone '{name}'")
        return zone

    def get_connection(self, zone_a: str, zone_b: str) -> Connection:
        """Return the connection between two zones, if any."""
        key = link_key(zone_a, zone_b)
        connection = self.connections.get(key)
        if connection is None:
            raise SimulationError(
                f"no connection between '{zone_a}' and '{zone_b}'"
            )
        return connection

    def neighbours(self, zone_name: str) -> list[Connection]:
        """Return the connections attached to a zone, in stable order."""
        found = [
            connection
            for connection in self.connections.values()
            if connection.zone_a == zone_name or connection.zone_b == zone_name
        ]
        return found

    def is_adjacent(self, zone_a: str, zone_b: str) -> bool:
        """Return True when both zones are directly connected."""
        return link_key(zone_a, zone_b) in self.connections

    @property
    def zone_count(self) -> int:
        """Return the number of zones."""
        return len(self.zones)
