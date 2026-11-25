"""Entry point of the Fly-in project.

Usage:
    python3 main.py <map_file> [--visual] [--animate] [--stats] [--check]

The standard output is the raw simulation (one line per turn, moves
space separated), exactly as required by the subject. Optional flags
add the colored visual representation, animations and metrics.
"""

from __future__ import annotations

import argparse
import sys

from errors import FlyInError
from parser import Parser
from simulation import Simulator
from validator import SimulationValidator
from visualizer import Visualizer


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command line interface."""
    argument_parser = argparse.ArgumentParser(
        prog="fly-in",
        description="Route drones through a zone network.",
    )
    argument_parser.add_argument("map_file", help="path to the map file")
    argument_parser.add_argument(
        "--visual",
        action="store_true",
        help="colored turn by turn view of the simulation",
    )
    argument_parser.add_argument(
        "--animate",
        action="store_true",
        help="animated network snapshots (implies --visual)",
    )
    argument_parser.add_argument(
        "--stats",
        action="store_true",
        help="print secondary metrics at the end",
    )
    argument_parser.add_argument(
        "--check",
        action="store_true",
        help="replay and validate the simulation before printing it",
    )
    return argument_parser


def run(argv: list[str] | None = None) -> int:
    """Run the program and return the process exit code."""
    arguments = build_argument_parser().parse_args(argv)
    try:
        instance = Parser().parse_file(arguments.map_file)
        instance.validate_topology()
        result = Simulator(instance).run()
        if arguments.check:
            report = SimulationValidator(instance).validate(result.turns)
            if not report.ok:
                for violation in report.violations:
                    print(f"ERROR: {violation}", file=sys.stderr)
                return 1
        if arguments.animate:
            Visualizer(instance).render_turns(result, animate=True)
            return 0
        if arguments.visual:
            Visualizer(instance).render_turns(result, animate=False)
            return 0
        for moves in result.turns:
            print(" ".join(moves))
        if arguments.stats:
            Visualizer(instance, use_color=False).render_summary(result)
        return 0
    except FlyInError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run())
