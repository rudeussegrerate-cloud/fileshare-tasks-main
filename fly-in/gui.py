"""Pygame graphical simulation of the Fly-in project.

The window shows the zone network, the connections, the zone types
with their icons (`[ ]` normal, `[X]` blocked, `[!]` restricted,
`[*]` priority) and the drones moving turn by turn.

pygame is imported lazily, inside the visualization loop only, so the
rest of the project (tests, lint, terminal modes) keeps working when
the library is not installed. The renderer itself is a pure object
and can be tested headlessly.
"""

from __future__ import annotations

from typing import Any

from instance import Instance
from simulation import SimulationResult

WINDOW_CAPTION = "Fly-in - graphical simulation"
FOOTER_TEXT = (
    "[SPACE] play/pause  [LEFT/RIGHT] step  [UP/DOWN] speed  [ESC] quit"
)
TWO_PI = 2 * 3.141592653589793


class GuiUnavailable(Exception):
    """Raised when the pygame dependency is unavailable."""


class ZonePalette:
    """RGB colors of the graphical view."""

    BACKGROUND = (16, 18, 24)
    LINK = (70, 76, 94)
    TEXT = (224, 228, 236)
    DARK_TEXT = (16, 18, 24)
    DRONE = (240, 244, 248)
    DRONE_EDGE = (30, 34, 44)
    IN_FLIGHT = (255, 170, 60)
    MOVED = (96, 226, 140)

    NAMED_COLORS: dict[str, tuple[int, int, int]] = {
        "black": (20, 20, 20),
        "red": (231, 76, 60),
        "green": (46, 204, 113),
        "yellow": (241, 196, 15),
        "blue": (52, 152, 219),
        "magenta": (170, 90, 200),
        "cyan": (38, 194, 180),
        "white": (236, 240, 241),
        "gray": (127, 140, 141),
        "grey": (127, 140, 141),
        "orange": (230, 126, 34),
        "purple": (142, 68, 173),
        "pink": (231, 84, 128),
        "brown": (146, 90, 54),
    }
    FALLBACK: tuple[tuple[int, int, int], ...] = (
        (231, 76, 60),
        (46, 204, 113),
        (241, 196, 15),
        (52, 152, 219),
        (170, 90, 200),
        (38, 194, 180),
    )
    TYPE_COLORS: dict[str, tuple[int, int, int]] = {
        "normal": (72, 132, 198),
        "blocked": (96, 100, 110),
        "restricted": (214, 92, 66),
        "priority": (232, 196, 60),
    }

    def resolve(self, color: str | None) -> tuple[int, int, int] | None:
        """Return the RGB tuple of a color name, deterministic."""
        if color is None:
            return None
        known = self.NAMED_COLORS.get(color.lower())
        if known is not None:
            return known
        index = 0
        for character in color:
            index += ord(character)
        return self.FALLBACK[index % len(self.FALLBACK)]

    def zone_fill(
        self, zone_type: str, color: str | None, is_start: bool, is_end: bool
    ) -> tuple[int, int, int]:
        """Return the fill color of one zone."""
        named = self.resolve(color)
        if named is not None:
            return named
        if is_start:
            return (46, 204, 113)
        if is_end:
            return (186, 110, 226)
        return self.TYPE_COLORS.get(zone_type, self.TYPE_COLORS["normal"])


class GuiRenderer:
    """Pure layout and drawing model of the graphical simulation.

    Positions, colors, icons and per-turn drone spots are computed
    here without touching pygame, so the class is testable headlessly.
    """

    CELL = 110
    MARGIN = 90
    RADIUS = 30
    DRONE_RADIUS = 9

    def __init__(self, instance: Instance) -> None:
        self.instance = instance
        self.palette = ZonePalette()
        self.positions = self._compute_positions()
        self.links = self._compute_links()

    def _compute_positions(self) -> dict[str, tuple[float, float]]:
        """Map zone coordinates to pixel centers."""
        zones = list(self.instance.network.zones.values())
        if not zones:
            return {}
        min_x = zones[0].x
        min_y = zones[0].y
        for zone in zones:
            if zone.x < min_x:
                min_x = zone.x
            if zone.y < min_y:
                min_y = zone.y
        return {
            zone.name: (
                float(GuiRenderer.MARGIN + (zone.x - min_x)
                      * GuiRenderer.CELL),
                float(GuiRenderer.MARGIN + (zone.y - min_y)
                      * GuiRenderer.CELL),
            )
            for zone in zones
        }

    def _compute_links(
        self,
    ) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        """Return the pixel segments of every connection."""
        segments: list[
            tuple[tuple[float, float], tuple[float, float]]
        ] = []
        for connection in self.instance.network.connections.values():
            first = self.positions.get(connection.zone_a)
            second = self.positions.get(connection.zone_b)
            if first is not None and second is not None:
                segments.append((first, second))
        return segments

    def canvas_size(self) -> tuple[int, int]:
        """Return the pixel size of the window."""
        if not self.positions:
            return (640, 480)
        width = 0.0
        height = 0.0
        for x, y in self.positions.values():
            if x > width:
                width = x
            if y > height:
                height = y
        return (
            int(width + GuiRenderer.MARGIN),
            int(height + GuiRenderer.MARGIN),
        )

    def icon_of(self, zone_name: str) -> str:
        """Return the type icon drawn inside one zone."""
        zone = self.instance.network.get_zone(zone_name)
        if zone.is_start:
            return "[S]"
        if zone.is_end:
            return "[E]"
        return {
            "normal": "[ ]",
            "blocked": "[X]",
            "restricted": "[!]",
            "priority": "[*]",
        }.get(zone.zone_type.value, "[ ]")

    def fill_of(self, zone_name: str) -> tuple[int, int, int]:
        """Return the fill color of one zone."""
        zone = self.instance.network.get_zone(zone_name)
        return self.palette.zone_fill(
            zone.zone_type.value,
            zone.color,
            zone.is_start,
            zone.is_end,
        )

    def replay_states(self, result: SimulationResult) -> list[dict[int, str]]:
        """Replay the tokens into per-drone logical positions.

        Each state maps a drone id to its logical position: a zone
        name, or a connection name while in 2-turn transit.
        """
        logical: dict[int, str] = {
            drone_id: self.instance.start
            for drone_id in range(1, self.instance.nb_drones + 1)
        }
        states: list[dict[int, str]] = [dict(logical)]
        for moves in result.turns:
            for token in moves:
                head, _, destination = token.partition("-")
                drone_id = self._drone_id_of(head)
                if drone_id is not None:
                    logical[drone_id] = destination
            states.append(dict(logical))
        return states

    @staticmethod
    def _drone_id_of(head: str) -> int | None:
        """Extract the drone id of a 'D12' token prefix."""
        if not head.startswith("D"):
            return None
        digits = head[1:]
        if not digits.isdigit():
            return None
        return int(digits)

    def movement_sets(self, result: SimulationResult) -> list[set[int]]:
        """Return the set of drone ids moving at every transition.

        The element at index k is the set of drones whose positions
        change between `states[k]` and `states[k + 1]`.
        """
        movements: list[set[int]] = []
        for moves in result.turns:
            ids: set[int] = set()
            for token in moves:
                head, _, _ = token.partition("-")
                drone_id = self._drone_id_of(head)
                if drone_id is not None:
                    ids.add(drone_id)
            movements.append(ids)
        return movements

    def center_of(self, logical: str) -> tuple[float, float]:
        """Pixel center of a zone, or link midpoint for transits."""
        position = self.positions.get(logical)
        if position is not None:
            return position
        parts = logical.split("-")
        if len(parts) == 2:
            first = self.positions.get(parts[0])
            second = self.positions.get(parts[1])
            if first is not None and second is not None:
                return (
                    (first[0] + second[0]) / 2,
                    (first[1] + second[1]) / 2,
                )
        return (10.0, 10.0)

    def drone_spots(
        self, state: dict[int, str]
    ) -> dict[int, tuple[float, float]]:
        """Pixel positions of every drone, spread around busy zones."""
        by_zone: dict[str, list[int]] = {}
        for drone_id in state:
            by_zone.setdefault(state[drone_id], []).append(drone_id)
        spots: dict[int, tuple[float, float]] = {}
        for logical, drone_ids in by_zone.items():
            center = self.center_of(logical)
            count = len(drone_ids)
            for order, drone_id in enumerate(drone_ids):
                spots[drone_id] = self._spread(center, order, count)
        return spots

    @staticmethod
    def _spread(
        center: tuple[float, float],
        order: int,
        count: int,
    ) -> tuple[float, float]:
        """Place one drone around a zone center without overlapping."""
        if count == 1:
            return center
        angle = TWO_PI * order / count
        offset = GuiRenderer.DRONE_RADIUS + 12
        return (
            center[0] + offset * GuiRenderer._cosine(angle),
            center[1] + offset * GuiRenderer._sine(angle),
        )

    @staticmethod
    def _cosine(angle: float) -> float:
        """Hand made cosine (Taylor series), enough at drone scale."""
        adjusted = angle - TWO_PI * (angle // TWO_PI)
        term = 1.0
        result = 1.0
        for step in range(1, 8):
            term *= -adjusted * adjusted / ((2 * step - 1) * (2 * step))
            result += term
        return result

    @staticmethod
    def _sine(angle: float) -> float:
        """Hand made sine (Taylor series), enough at drone scale."""
        adjusted = angle - TWO_PI * (angle // TWO_PI)
        term = adjusted
        result = adjusted
        for step in range(1, 8):
            term *= -adjusted * adjusted / ((2 * step) * (2 * step + 1))
            result += term
        return result


class PygameVisualizer:
    """Interactive pygame window replaying the simulation.

    Drone movements are interpolated between turns so every glide is
    clearly visible, and the reading speed is adjustable.
    """

    SPEEDS: list[tuple[str, int]] = [
        ("lent", 1500),
        ("normal", 900),
        ("rapide", 500),
        ("turbo", 250),
    ]

    def __init__(self, instance: Instance, result: SimulationResult) -> None:
        self.instance = instance
        self.result = result
        self.renderer = GuiRenderer(instance)
        self.states = self.renderer.replay_states(result)
        self.movements = self.renderer.movement_sets(result)

    def run(self) -> None:
        """Run the replay loop until the window is closed."""
        pygame = self._import_pygame()
        pygame.init()
        size = self.renderer.canvas_size()
        screen = pygame.display.set_mode(size)
        pygame.display.set_caption(WINDOW_CAPTION)
        font = pygame.font.SysFont(None, 22)
        clock = pygame.time.Clock()
        last = len(self.states) - 1
        index = 0
        playing = True
        speed_level = 1
        running = True
        progress = 0.0
        while running:
            elapsed = clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif event.key == pygame.K_RIGHT:
                        playing = False
                        progress = 0.0
                        if index < last:
                            index += 1
                    elif event.key == pygame.K_LEFT:
                        playing = False
                        progress = 0.0
                        index = max(index - 1, 0)
                    elif event.key == pygame.K_SPACE:
                        if index >= last:
                            index = 0
                        playing = not playing
                        progress = 0.0
                    elif event.key == pygame.K_UP:
                        speed_level = min(
                            speed_level + 1, len(self.SPEEDS) - 1
                        )
                    elif event.key == pygame.K_DOWN:
                        speed_level = max(speed_level - 1, 0)
            if playing and index < last:
                progress += elapsed / self.SPEEDS[speed_level][1]
                if progress >= 1.0:
                    progress = 0.0
                    index = min(index + 1, last)
            elif index >= last:
                progress = 1.0
            else:
                progress = 0.0
            self._draw(screen, font, pygame, index, progress, speed_level)
            pygame.display.flip()
        pygame.quit()

    @staticmethod
    def _import_pygame() -> Any:
        """Import pygame lazily with an explicit error message."""
        try:
            import pygame
        except ImportError as error:
            raise GuiUnavailable(
                "pygame is required for --gui: run 'make install' "
                "or 'poetry install', or use --visual instead"
            ) from error
        return pygame

    def _draw(
        self,
        screen: Any,
        font: Any,
        pygame: Any,
        index: int,
        progress: float,
        speed_level: int,
    ) -> None:
        """Paint the current (interpolated) frame of the simulation."""
        palette = self.renderer.palette
        screen.fill(palette.BACKGROUND)
        for first, second in self.renderer.links:
            pygame.draw.line(screen, palette.LINK, first, second, 3)
        for name, position in self.renderer.positions.items():
            radius = GuiRenderer.RADIUS
            pygame.draw.circle(screen, self.renderer.fill_of(name),
                               position, radius)
            pygame.draw.circle(screen, palette.TEXT, position, radius, 2)
            icon = font.render(self.renderer.icon_of(name), True,
                               palette.DARK_TEXT)
            icon_rect = icon.get_rect(center=position)
            screen.blit(icon, icon_rect)
            label = font.render(name, True, palette.TEXT)
            label_rect = label.get_rect(
                center=(position[0], position[1] + radius + 12)
            )
            screen.blit(label, label_rect)
        state = self.states[index]
        target = min(index + 1, len(self.states) - 1)
        nearest = state if progress < 0.5 else self.states[target]
        starts = self.renderer.drone_spots(state)
        ends = self.renderer.drone_spots(self.states[target])
        movers: set[int] = set()
        if index < len(self.movements):
            movers = self.movements[index]
        for drone_id, start in starts.items():
            end = ends.get(drone_id, start)
            spot = (
                start[0] + (end[0] - start[0]) * progress,
                start[1] + (end[1] - start[1]) * progress,
            )
            color = palette.DRONE
            if nearest[drone_id] not in self.renderer.positions:
                color = palette.IN_FLIGHT
            if progress > 0.0 and drone_id in movers:
                pygame.draw.circle(screen, palette.MOVED, spot,
                                   GuiRenderer.DRONE_RADIUS + 5, 2)
            pygame.draw.circle(screen, palette.DRONE_EDGE, spot,
                               GuiRenderer.DRONE_RADIUS)
            pygame.draw.circle(screen, color, spot,
                               GuiRenderer.DRONE_RADIUS - 2)
        speed_name = self.SPEEDS[speed_level][0]
        header = font.render(
            f"Fly-in - tour {index}/{len(self.states) - 1}", True,
            palette.TEXT
        )
        screen.blit(header, (16, 12))
        footer = font.render(
            f"{FOOTER_TEXT}  - vitesse: {speed_name}",
            True, palette.TEXT,
        )
        screen.blit(footer, (16, self.renderer.canvas_size()[1] - 30))


def launch_graphical_simulation(
    instance: Instance, result: SimulationResult
) -> None:
    """Open the pygame window replaying the simulation."""
    PygameVisualizer(instance, result).run()
