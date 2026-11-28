"""Entry point of the Fly-in project.

Usage:
    python3 main.py <map_file> [--visual] [--animate] [--gui] [--stats]
                    [--check]

The standard output is the raw simulation (one line per turn, moves
space separated), exactly as required by the subject. Optional flags
add the colored terminal view, the pygame window, animations and
metrics. The command line interface is hand made (no argparse).
"""

from __future__ import annotations

import sys

from errors import FlyInError
from gui import GuiUnavailable, launch_graphical_simulation
from parser import Parser
from simulation import Simulator
from validator import SimulationValidator
from visualizer import Visualizer

USAGE = (
    "usage: main.py <map_file> [--visual] [--animate] [--gui] "
    "[--stats] [--check]"
)


class UsageError(FlyInError):
    """Raised when command line arguments are invalid."""


class CommandLineArguments:
    """Hand made argument holder (replaces argparse)."""

    def __init__(self) -> None:
        self.map_file: str | None = None
        self.visual = False
        self.animate = False
        self.gui = False
        self.stats = False
        self.check = False


def parse_arguments(tokens: list[str]) -> CommandLineArguments:
    """Parse the command line tokens manually.

    Raises:
        UsageError: on any unknown, duplicate or missing argument.
    """
    arguments = CommandLineArguments()
    for token in tokens:
        if token == "--animate":
            arguments.animate = True
        elif token == "--visual":
            arguments.visual = True
        elif token == "--gui":
            arguments.gui = True
        elif token == "--stats":
            arguments.stats = True
        elif token == "--check":
            arguments.check = True
        elif token.startswith("--"):
            raise UsageError(f"unknown option '{token}'")
        elif arguments.map_file is None:
            arguments.map_file = token
        else:
            raise UsageError(f"unexpected argument '{token}'")
    if arguments.map_file is None:
        raise UsageError("missing map file argument")
    return arguments


def run(argv: list[str] | None = None) -> int:
    """Run the program and return the process exit code."""
    tokens = list(sys.argv[1:]) if argv is None else list(argv)
    try:
        arguments = parse_arguments(tokens)
    except UsageError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 1
    try:
        instance = Parser().parse_file(arguments.map_file or "")
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
        if arguments.gui:
            try:
                launch_graphical_simulation(instance, result)
            except GuiUnavailable as error:
                print(f"ERROR: {error}", file=sys.stderr)
                return 1
            Visualizer(instance, use_color=False).render_summary(result)
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
