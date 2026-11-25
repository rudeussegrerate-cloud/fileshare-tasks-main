"""Zone model of the Fly-in network.

A zone is a node of the drone network. Each zone has a type which
drives the cost (in simulation turns) of moving a drone into it.
Zone types are hand made objects (no Enum).
"""

from __future__ import annotations

MAX_ZONE_TYPES_VARIANTS = 4
"""Number of distinct zone types accepted by the parser."""


class ZoneType:
    """Hand made zone type object (replaces an enumeration).

    Attributes:
        value: string written in map files.
        entry_cost: turns needed to move a drone into such a zone.
        enterable: whether drones may enter it at all.
    """

    NORMAL: "ZoneType"
    BLOCKED: "ZoneType"
    RESTRICTED: "ZoneType"
    PRIORITY: "ZoneType"

    def __init__(
        self, value: str, entry_cost: int, enterable: bool
    ) -> None:
        self.value = value
        self.entry_cost = entry_cost
        self.enterable = enterable

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ZoneType) and other.value == self.value

    def __hash__(self) -> int:
        return hash(self.value)


ZoneType.NORMAL = ZoneType("normal", 1, True)
ZoneType.BLOCKED = ZoneType("blocked", 0, False)
ZoneType.RESTRICTED = ZoneType("restricted", 2, True)
ZoneType.PRIORITY = ZoneType("priority", 1, True)

ALL_ZONE_TYPES: list[ZoneType] = [
    ZoneType.NORMAL,
    ZoneType.BLOCKED,
    ZoneType.RESTRICTED,
    ZoneType.PRIORITY,
]


def zone_type_from_name(name: str) -> ZoneType | None:
    """Return the zone type object matching a map file string."""
    for zone_type in ALL_ZONE_TYPES:
        if zone_type.value == name:
            return zone_type
    return None


class Zone:
    """A zone (node) of the network.

    Attributes:
        name: unique zone identifier, without dashes or spaces.
        x: horizontal coordinate (integer).
        y: vertical coordinate (integer).
        zone_type: type of the zone (movement cost driver).
        color: optional color used by the visual representations.
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

        Start and end hubs are exempt from capacity limits: every
        drone may share them, and declared max_drones is ignored.
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
        return f"{kind} {self.name} ({self.x}, {self.y}) {self.zone_type}"
