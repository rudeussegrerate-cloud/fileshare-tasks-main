"""Drone state used by the simulation engine."""

from __future__ import annotations

from connection import Connection


class Transit:
    """A two-turn crossing towards a restricted zone.

    Attributes:
        connection: connection being traversed.
        destination: restricted zone reached at `arrival_turn`.
        arrival_turn: turn at which the drone must land.
    """

    def __init__(
        self,
        connection: Connection,
        destination: str,
        arrival_turn: int,
    ) -> None:
        self.connection = connection
        self.destination = destination
        self.arrival_turn = arrival_turn

    @property
    def token(self) -> str:
        """Return the output token printed while in flight."""
        return self.connection.name


class Drone:
    """Mutable state of one drone during the simulation.

    Attributes:
        drone_id: 1-based unique identifier.
        path: assigned zone route from start to end.
        cursor: index of the current position inside `path`.
        position: current zone name (while not in flight).
        transit: in-flight state, or None.
        arrival_turn: turn at which the drone reached the end zone.
        stuck_since: turn at which the drone last failed to move.
    """

    def __init__(self, drone_id: int, path: list[str]) -> None:
        self.drone_id = drone_id
        self.path = path
        self.cursor = 0
        self.position = path[0]
        self.transit: Transit | None = None
        self.arrival_turn: int | None = None
        self.stuck_since: int | None = None
        self.replans: int = 0

    @property
    def target_index(self) -> int:
        """Return the index of the next zone on the assigned path."""
        return self.cursor + 1

    def commit_move(self, new_index: int) -> None:
        """Advance the drone to the zone at `new_index` on its path."""
        self.cursor = new_index
        self.position = self.path[new_index]
        self.stuck_since = None

    def is_delivered(self) -> bool:
        """Return True once the drone reached the end zone."""
        return self.position == self.path[-1] and self.cursor == len(
            self.path
        ) - 1 and self.transit is None
