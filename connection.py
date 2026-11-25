"""Connection model (edge) of the Fly-in network."""

from __future__ import annotations

from datastructures import link_key


class Connection:
    """A bidirectional connection between two zones.

    Attributes:
        zone_a: first zone name.
        zone_b: second zone name.
        max_link_capacity: number of drones that may traverse this
            connection simultaneously (from both directions).
    """

    def __init__(
        self,
        zone_a: str,
        zone_b: str,
        max_link_capacity: int | None = None,
    ) -> None:
        self.zone_a = zone_a
        self.zone_b = zone_b
        self.max_link_capacity = max_link_capacity

    @property
    def name(self) -> str:
        """Return the connection name as written in the map file."""
        return f"{self.zone_a}-{self.zone_b}"

    @property
    def capacity(self) -> int:
        """Return the traversal limit (default 1)."""
        return self.max_link_capacity if self.max_link_capacity is not None else 1

    def key(self) -> tuple[str, str]:
        """Return a hashable key used to detect duplicate connections."""
        return link_key(self.zone_a, self.zone_b)

    def other(self, zone: str) -> str:
        """Return the zone at the other end of this connection."""
        if zone == self.zone_a:
            return self.zone_b
        return self.zone_a

    def __repr__(self) -> str:
        return f"connection: {self.name} [cap={self.capacity}]"
