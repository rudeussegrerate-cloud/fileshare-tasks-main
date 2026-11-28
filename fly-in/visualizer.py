"""Colored terminal visual representation of the simulation.

Provides:
  * a color resolver mapping any zone color name (single word) to an
    ANSI color, with a deterministic fallback palette;
  * a verbose turn by turn view showing drone moves with colors;
  * a compact snapshot of the network with current drone counts;
  * a summary of the secondary metrics from the subject.
"""

from __future__ import annotations

import os
import time

from instance import Instance
from simulation import SimulationResult

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CLEAR_SCREEN = "\033[2J\033[H"

_ANSI_COLORS: dict[str, str] = {
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "gray": "\033[90m",
    "grey": "\033[90m",
    "brightred": "\033[91m",
    "brightgreen": "\033[92m",
    "brightyellow": "\033[93m",
    "brightblue": "\033[94m",
    "brightmagenta": "\033[95m",
    "brightcyan": "\033[96m",
}
_PALETTE: tuple[str, ...] = (
    "\033[31m", "\033[32m", "\033[33m", "\033[34m",
    "\033[35m", "\033[36m", "\033[91m", "\033[94m",
)
_ZONE_ICONS = {
    "normal": "[ ]",
    "blocked": "[X]",
    "restricted": "[!]",
    "priority": "[*]",
}


class Visualizer:
    """Renders simulation results to colored terminal output."""

    def __init__(self, instance: Instance, use_color: bool = True) -> None:
        self.instance = instance
        self.use_color = use_color and self._color_allowed()

    @staticmethod
    def _color_allowed() -> bool:
        """Respect the NO_COLOR convention; --visual forces colors on."""
        return os.environ.get("NO_COLOR", "") == ""

    def _color(self, color: str | None) -> str:
        """Return the ANSI prefix for a color name, deterministic."""
        if not self.use_color or color is None:
            return ""
        return _ANSI_COLORS.get(color.lower(), "")

    def _fallback_color(self, name: str) -> str:
        """Deterministic palette color for unknown color names."""
        if not self.use_color:
            return ""
        index = sum(ord(char) for char in name) % len(_PALETTE)
        return _PALETTE[index]

    def paint(self, text: str, color: str | None) -> str:
        """Wrap text with the ANSI color of a zone, if any."""
        if color is None:
            return text
        prefix = self._color(color) or self._fallback_color(color)
        return f"{prefix}{text}{RESET}" if prefix else text

    # ------------------------------------------------------------------
    def render_turns(self, result: SimulationResult, animate: bool
                     ) -> None:
        """Print the turn by turn colored view of the simulation."""
        position: dict[str, int] = {self.instance.start: (
            self.instance.nb_drones
        )}
        for turn_no, moves in enumerate(result.turns, start=1):
            if animate:
                self._animate_header()
            tokens: list[str] = []
            for move in moves:
                drone_id, _, destination = move.partition("-")
                tokens.append(
                    f"{BOLD}{drone_id}{RESET}->"
                    f"{self._painted_destination(destination)}"
                )
                self._apply_move(position, destination)
            if animate:
                self.render_snapshot(position, turn_no)
                time.sleep(0.25)
            header = f"{DIM}turn {turn_no}{RESET}" if self.use_color else (
                f"turn {turn_no}"
            )
            print(f"{header}  " + " ".join(tokens) if tokens
                  else f"{header}  (no movement)")
        self.render_summary(result)

    def _painted_destination(self, destination: str) -> str:
        """Colorize a destination zone or connection name."""
        zone = self.instance.network.zones.get(destination)
        if zone is not None:
            return self.paint(destination, zone.color)
        parts = destination.split("-")
        zone_names = [
            part for part in parts if part in self.instance.network.zones
        ]
        color = zone_names[0] and self.instance.network.get_zone(
            zone_names[0]
        ).color
        return self.paint(destination, color)

    @staticmethod
    def _apply_move(position: dict[str, int], destination: str) -> None:
        """Approximate live position tracking for the animated view."""
        if "-" in destination:
            return
        position[destination] = position.get(destination, 0) + 1

    def render_snapshot(self, position: dict[str, int], turn: int) -> None:
        """Print the network state after `turn` turns."""
        print(CLEAR_SCREEN, end="")
        print(f"{BOLD}Fly-in{RESET} after turn {turn}")
        for name, zone in self.instance.network.zones.items():
            icon = _ZONE_ICONS[zone.zone_type.value]
            count = position.get(name, 0)
            drones = f"{count} drone{'s' if count != 1 else ''}"
            layout = f"{icon} {name} ({zone.x},{zone.y}) {drones}"
            print("  " + self.paint(layout, zone.color))

    def _animate_header(self) -> None:
        """Prepare the screen for an animated frame."""
        print(CLEAR_SCREEN, end="")
        print(f"{BOLD}Fly-in{RESET} simulation")

    def render_summary(self, result: SimulationResult) -> None:
        """Print secondary evaluation metrics."""
        lines = [
            f"total turns       : {result.total_turns}",
            f"drones delivered  : {len(result.arrival_turns)}",
            f"total moves       : {result.total_moves}",
            f"avg turns / drone : "
            f"{result.average_turns_per_drone:.2f}",
            f"total path cost   : {result.total_path_cost}",
        ]
        header = "simulation summary"
        print()
        print(f"{BOLD}{header}{RESET}" if self.use_color else header)
        for line in lines:
            print(line)
