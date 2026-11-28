"""Custom exceptions for the Fly-in project."""


class FlyInError(Exception):
    """Base class for all Fly-in project errors."""


class ParseError(FlyInError):
    """Raised when an input map file violates the expected format.

    Attributes:
        line_no: 1-based line number where the error occurred, or None
            when the error spans the whole file (e.g. duplicate hubs).
    """

    def __init__(self, message: str, line_no: int | None = None) -> None:
        location = f"line {line_no}: " if line_no is not None else ""
        super().__init__(f"{location}{message}")
        self.line_no = line_no


class SimulationError(FlyInError):
    """Raised when the simulation cannot reach a valid solution."""


class SimulationIntegrityError(SimulationError):
    """Raised when a simulation step would violate the movement rules."""
