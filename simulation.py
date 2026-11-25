"""Turn based simulation engine for the Fly-in project.

Scheduling principles (see the subject):
  * drones move simultaneously: drones leaving a zone free its
    capacity during the same turn, so swaps are allowed;
  * a zone must have room for an arriving drone once out-movers left;
  * entering a restricted zone starts a 2-turn transit: the drone
    occupies the connection on the first turn and MUST land on the
    next turn; the landing zone is therefore reserved in advance and
    landings are never cancelled;
  * a drone may always stay in place to wait.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from connection import Connection
from drone import Drone, Transit
from errors import SimulationError, SimulationIntegrityError
from instance import Instance
from network import Network
from pathfinding import (
    PathPlanner,
    PenaltyState,
    ShortestPathFinder,
)
from planner import PathAssigner
from zone import ZoneType

Action = tuple[str, str]
"""A committed action: ("zone", zone_name) or ("link", connection)."""


@dataclass
class SimulationResult:
    """Outcome of a full simulation.

    Attributes:
        turns: one list of per-drone move tokens per turn.
        assignments: path assigned to each drone id (index 0 = D1).
        arrival_turns: drone id -> delivery turn.
        total_path_cost: sum of the costs of the assigned paths.
    """

    turns: list[list[str]] = field(default_factory=list)
    assignments: list[list[str]] = field(default_factory=list)
    arrival_turns: dict[int, int] = field(default_factory=dict)
    total_path_cost: int = 0

    @property
    def total_turns(self) -> int:
        """Number of simulation turns needed to deliver every drone."""
        return len(self.turns)

    @property
    def total_moves(self) -> int:
        """Total number of individual drone moves."""
        return sum(len(moves) for moves in self.turns)

    @property
    def average_turns_per_drone(self) -> float:
        """Average delivery turn over all drones."""
        if not self.arrival_turns:
            return 0.0
        return sum(self.arrival_turns.values()) / len(self.arrival_turns)


class Simulator:
    """Runs the simulation of one parsed instance."""

    STUCK_THRESHOLD = 4
    MAX_REPLANS_PER_DRONE = 3

    def __init__(self, instance: Instance) -> None:
        self.instance = instance
        self.network: Network = instance.network
        self.planner = PathPlanner(
            self.instance.network, instance.start, instance.end
        )
        self.path_options = self.planner.compute_paths()
        self.assigner = PathAssigner(instance)
        self.drone_ids: list[int] = list(range(1, instance.nb_drones + 1))

    def run(self) -> SimulationResult:
        """Simulate the whole fleet and return the turn by turn result."""
        assignment = self.assigner.assign(self.path_options)
        drones = [
            Drone(drone_id, list(self.path_options[index].zones))
            for drone_id, index in zip(self.drone_ids, assignment)
        ]
        result = SimulationResult(
            assignments=[
                list(self.path_options[index].zones) for index in assignment
            ],
            total_path_cost=sum(
                self.path_options[index].cost for index in assignment
            ),
        )
        self._simulate(drones, result)
        return result

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def _simulate(self, drones: list[Drone], result: SimulationResult) -> None:
        """Run turns until every drone is delivered."""
        occupancy: Counter[str] = Counter(
            {self.instance.start: len(drones)}
        )
        longest = max(
            (self._path_cost(drone.path) for drone in drones), default=1
        )
        overtime = max(400, 12 * longest + 4 * len(drones))
        turn = 0
        while not all(drone.is_delivered() for drone in drones):
            turn += 1
            if turn > overtime:
                raise SimulationError(
                    "simulation exceeded the maximum number of turns; "
                    "the fleet appears deadlocked"
                )
            result.turns.append(self._run_turn(drones, occupancy, turn))
            self._refresh_occupancy(occupancy, drones)
            self._try_replan(drones, turn)
        result.arrival_turns = {
            drone.drone_id: delivered
            for drone in drones
            if (delivered := drone.arrival_turn) is not None
        }

    def _run_turn(
        self,
        drones: list[Drone],
        occupancy: Counter[str],
        turn: int,
    ) -> list[str]:
        """Execute one simulation turn and return its move tokens."""
        landings = self._collect_landings(drones, turn)
        waiting = [
            drone for drone in drones
            if drone.transit is None and not drone.is_delivered()
        ]
        candidates = self._decide_all(waiting)
        committed = self._repair(dict(candidates), occupancy, waiting)
        landing_tokens = [
            f"D{drone.drone_id}-{drone.transit.destination}"
            for drone in landings if drone.transit is not None
        ]
        moves: list[str] = []
        for drone in waiting:
            action = committed.get(drone.drone_id)
            if action is None:
                if drone.stuck_since is None:
                    drone.stuck_since = turn
                continue
            drone.stuck_since = None
            moves.append(f"D{drone.drone_id}-{action[1]}")
            if action[0] == "link":
                self._board(drone, turn)
            else:
                drone.commit_move(drone.target_index)
                if drone.position == self.instance.end:
                    drone.arrival_turn = turn
        for drone in landings:
            self._land(drone, turn)
        return landing_tokens + moves

    def _refresh_occupancy(
        self, occupancy: Counter[str], drones: list[Drone]
    ) -> None:
        """Rebuild zone occupancy from the current drone positions."""
        occupancy.clear()
        occupancy.update(
            Counter(
                drone.position
                for drone in drones
                if drone.transit is None
            )
        )

    def _collect_landings(
        self, drones: list[Drone], turn: int
    ) -> list[Drone]:
        """Drones in flight whose landing turn is now (mandatory)."""
        landings: list[Drone] = []
        for drone in drones:
            transit = drone.transit
            if transit is None:
                continue
            if transit.arrival_turn != turn:
                raise SimulationIntegrityError(
                    f"D{drone.drone_id} is stranded on a connection"
                )
            landings.append(drone)
        return landings

    def _decide_all(self, waiting: list[Drone]) -> list[tuple[int, Action]]:
        """Build the candidate action of every waiting drone."""
        candidates: list[tuple[int, Action]] = []
        for drone in self._move_order(waiting):
            action = self._decide(drone)
            if action is not None:
                candidates.append((drone.drone_id, action))
        return candidates

    @staticmethod
    def _move_order(waiting: list[Drone]) -> list[Drone]:
        """Sort drones: the farthest from the goal moves first."""
        return sorted(
            waiting,
            key=lambda drone: (
                drone.target_index - len(drone.path),
                drone.drone_id,
            ),
        )

    def _decide(self, drone: Drone) -> Action | None:
        """Choose the next action of a waiting drone, or None to stay."""
        if drone.target_index >= len(drone.path):
            return None
        target = self.network.get_zone(drone.path[drone.target_index])
        if not target.enterable:
            return None
        if target.zone_type is ZoneType.RESTRICTED:
            return ("link", self._transit_name(drone))
        return ("zone", target.name)

    def _transit_name(self, drone: Drone) -> str:
        """Connection name while flying towards a restricted zone."""
        connection = self.network.get_connection(
            drone.position, drone.path[drone.target_index]
        )
        return connection.name

    # ------------------------------------------------------------------
    # Conflict resolution
    # ------------------------------------------------------------------
    def _repair(
        self,
        committed: dict[int, Action],
        occupancy: Counter[str],
        waiting: list[Drone],
    ) -> dict[int, Action]:
        """Drop conflicting moves, lowest priority drone first.

        The projected end-of-turn occupancy is rebuilt until every zone
        fits its capacity, every link fits its traversal limit and
        every landing reserved this turn has room on the next turn.
        """
        by_id = {drone.drone_id: drone for drone in waiting}
        while True:
            occ = self._project(occupancy, committed, by_id)
            landers = self._count_landers(committed, by_id)
            victim = self._find_violation(committed, by_id, occ, landers)
            if victim is None:
                return committed
            del committed[victim]

    def _project(
        self,
        occupancy: Counter[str],
        committed: dict[int, Action],
        by_id: dict[int, Drone],
    ) -> Counter[str]:
        """Return the end-of-turn occupancy implied by committed moves."""
        occ = Counter(occupancy)
        for drone_id, action in committed.items():
            drone = by_id[drone_id]
            occ[drone.position] -= 1
            if action[0] == "zone":
                occ[action[1]] += 1
        return occ

    def _count_landers(
        self, committed: dict[int, Action], by_id: dict[int, Drone]
    ) -> Counter[str]:
        """Transits initiated this turn, grouped by landing zone."""
        landers: Counter[str] = Counter()
        for drone_id, action in committed.items():
            if action[0] != "link":
                continue
            drone = by_id[drone_id]
            landers[drone.path[drone.target_index]] += 1
        return landers

    def _find_violation(
        self,
        committed: dict[int, Action],
        by_id: dict[int, Drone],
        occ: Counter[str],
        landers: Counter[str],
    ) -> int | None:
        """Return the drone id of the move to cancel, or None."""
        order = sorted(committed, key=lambda i: self._drop_key(by_id, i))
        for drone_id in order:
            drone = by_id[drone_id]
            kind, target = committed[drone_id]
            destination = (
                target if kind == "zone"
                else drone.path[drone.target_index]
            )
            if kind == "link":
                capacity = self.network.get_zone(destination).capacity
                if capacity is not None and (
                    occ[destination] + landers[destination] > capacity
                ):
                    return drone_id
            else:
                capacity = self.network.get_zone(destination).capacity
                if capacity is not None and occ[destination] > capacity:
                    return drone_id
            link = self._link_of(drone, destination)
            if link is not None and (
                self._link_usage(committed, by_id, link) > link.capacity
            ):
                return drone_id
        return None

    def _link_of(
        self, drone: Drone, destination: str
    ) -> Connection | None:
        """Return the connection traversed by a committed move, or None."""
        try:
            return self.network.get_connection(
                drone.position, destination
            )
        except SimulationError:
            return None

    @staticmethod
    def _drop_key(by_id: dict[int, Drone], drone_id: int) -> tuple[int, int]:
        """Cancel order: closest to their goal first, ties by id desc."""
        drone = by_id[drone_id]
        remaining = len(drone.path) - drone.target_index
        return (remaining, -drone_id)

    def _link_usage(
        self,
        committed: dict[int, Action],
        by_id: dict[int, Drone],
        link: Connection,
    ) -> int:
        """Count drones traversing one connection during this turn."""
        usage = 0
        for drone_id in committed:
            drone = by_id[drone_id]
            if drone.target_index >= len(drone.path):
                continue
            try:
                connection = self.network.get_connection(
                    drone.position, drone.path[drone.target_index]
                )
            except SimulationError:
                continue
            if connection.key() == link.key():
                usage += 1
        return usage

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def _board(self, drone: Drone, turn: int) -> None:
        """Start a 2-turn transit towards a restricted zone."""
        destination = drone.path[drone.target_index]
        connection = self.network.get_connection(
            drone.position, destination
        )
        drone.transit = Transit(connection, destination, turn + 1)
        drone.position = connection.name

    def _land(self, drone: Drone, turn: int) -> None:
        """Complete a transit onto its restricted destination."""
        transit = drone.transit
        if transit is None:
            raise SimulationIntegrityError("landing without transit")
        drone.transit = None
        drone.commit_move(drone.target_index)
        if drone.position == self.instance.end:
            drone.arrival_turn = turn

    def _path_cost(self, path: list[str]) -> int:
        """Total movement cost of a zone path."""
        return sum(
            self.network.get_zone(zone).entry_cost for zone in path[1:]
        )

    # ------------------------------------------------------------------
    # Anti deadlock replanning
    # ------------------------------------------------------------------
    def _try_replan(self, drones: list[Drone], turn: int) -> None:
        """Re-route drones blocked for several consecutive turns."""
        blocked: Counter[str] = Counter(
            drone.position
            for drone in drones
            if self._needs_replan(drone, turn)
        )
        state = PenaltyState(
            zone_penalty={
                zone: count * self.STUCK_THRESHOLD
                for zone, count in blocked.items()
            }
        )
        finder = ShortestPathFinder(self.network)
        for drone in drones:
            if not self._needs_replan(drone, turn):
                continue
            new_path = finder.shortest_path(
                drone.position, self.instance.end, state
            )
            if new_path is None:
                continue
            if list(new_path) == drone.path[drone.cursor:]:
                continue
            if self._path_cost(list(new_path)) >= self._path_cost(
                drone.path[drone.cursor:]
            ):
                continue
            drone.replans += 1
            drone.path = drone.path[: drone.cursor] + list(new_path)
            drone.stuck_since = turn

    def _needs_replan(self, drone: Drone, turn: int) -> bool:
        """Really blocked drone (advanced once, then stopped many turns)."""
        if drone.is_delivered() or drone.transit is not None:
            return False
        if drone.cursor == 0:
            return False
        if drone.replans >= self.MAX_REPLANS_PER_DRONE:
            return False
        return (
            drone.stuck_since is not None
            and turn - drone.stuck_since >= self.STUCK_THRESHOLD
        )
