"""Zone model of the Fly-in network.

A zone is a node of the drone network. Each zone has a type which drives
the cost (in simulation turns) of moving a drone into it.
"""

from __future__ import annotations

from enum import Enum

MAX_ZONE_TYPES_VARIANTS = 4
"""Number of distinct zone types accepted by the parser."""


class ZoneType(str, Enum):
    """Types of zones with their movement cost in turns."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

    @property
    def entry_cost(self) -> int:
        """Return the number of turns needed to move into such a zone."""
        if self is ZoneType.RESTRICTED:
            return 2
        if self is ZoneType.BLOCKED:
            return 0
        return 1

    @property
    def enterable(self) -> bool:
        """Return True when drones are allowed to enter this zone type."""
        return self is not ZoneType.BLOCKED


class Zone:
    """A zone (node) of the network.

    Attributes:
        name: unique zone identifier, without dashes or spaces.
        x: horizontal coordinate (integer).
        y: vertical coordinate (integer).
        zone_type: type of the zone (movement cost driver).
        color: optional color used for the colored terminal output.
        max_drones: raw capacity metadata from the file (may be None).
    """

    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        zone_type: ZoneType = ZoneType.NORMAL,
        color: str | None = None,
        max_drones: int | None = None,
        is_start: bool = False,
        is_end: bool = False,
    ) -> None:
        self.name = name
        self.x = x
        self.y = y
        self.zone_type = zone_type
        self.color = color
        self.max_drones = max_drones
        self.is_start = is_start
        self.is_end = is_end

    @property
    def capacity(self) -> int | None:
        """Return the occupancy limit, or None when unlimited.

        Start and end hubs are exempt from capacity limits: every drone
        may share them, and any declared max_drones metadata is ignored.
        """
        if self.is_start or self.is_end:
            return None
        return self.max_drones if self.max_drones is not None else 1

    @property
    def entry_cost(self) -> int:
        """Return the turn cost of moving a drone into this zone."""
        return self.zone_type.entry_cost

    @property
    def enterable(self) -> bool:
        """Return True when drones may enter this zone."""
        return self.zone_type.enterable

    def __repr__(self) -> str:
        kind = "start_hub" if self.is_start else (
            "end_hub" if self.is_end else "hub"
        )
        return f"{kind} {self.name} ({self.x}, {self.y}) {self.zone_type.value}"
