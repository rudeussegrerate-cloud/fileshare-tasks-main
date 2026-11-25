"""Parser for the Fly-in map format.

The format is line based:

    nb_drones: <n>
    start_hub: <name> <x> <y> [k=v ...]
    end_hub: <name> <x> <y> [k=v ...]
    hub: <name> <x> <y> [k=v ...]
    connection: <name1>-<name2> [k=v ...]

Comments start with '#' and blank lines are ignored. Any invalid input
raises a ParseError carrying the offending line number.
"""

from __future__ import annotations

import re

from connection import Connection
from errors import ParseError
from instance import Instance
from network import Network
from zone import Zone, ZoneType

_DRONE_PATTERN = re.compile(r"nb_drones:\s*(\d+)$")
_ZONE_PATTERN = re.compile(
    r"(start_hub|end_hub|hub):\s+(\S+)\s+(-?\d+)\s+(-?\d+)\s*(\[.*\])?\s*$"
)
_CONNECTION_PATTERN = re.compile(
    r"connection:\s+(\S+)\s*(\[.*\])?\s*$"
)
_VALID_ZONE_KEYS = ("zone", "color", "max_drones")
_VALID_LINK_KEYS = ("max_link_capacity",)
_ZONE_TYPES = {ztype.value for ztype in ZoneType}


class Parser:
    """Parse a map file content into an Instance."""

    def parse(self, content: str) -> Instance:
        """Parse the full content of a map file.

        Raises:
            ParseError: on any structural, syntactic or semantic issue.
        """
        network = Network()
        start: str | None = None
        end: str | None = None
        nb_drones: int | None = None
        for line_no, raw_line in enumerate(content.splitlines(), start=1):
            line = self._strip_comment(raw_line).strip()
            if not line:
                continue
            if nb_drones is None:
                nb_drones = self._parse_nb_drones(line, line_no)
                continue
            if line.startswith("hub:") or line.startswith(
                "start_hub:"
            ) or line.startswith("end_hub:"):
                zone = self._parse_zone(line, line_no)
                network.add_zone(zone, line_no)
                if zone.is_start:
                    if start is not None:
                        raise ParseError(
                            "multiple start_hub definitions", line_no
                        )
                    start = zone.name
                elif zone.is_end:
                    if end is not None:
                        raise ParseError(
                            "multiple end_hub definitions", line_no
                        )
                    end = zone.name
            elif line.startswith("connection:"):
                connection = self._parse_connection(line, line_no)
                network.add_connection(connection, line_no)
            else:
                raise ParseError(f"unknown directive '{line}'", line_no)
        if nb_drones is None:
            raise ParseError("missing nb_drones first line")
        if start is None:
            raise ParseError("missing start_hub definition")
        if end is None:
            raise ParseError("missing end_hub definition")
        return Instance(nb_drones, network, start, end)

    def parse_file(self, path: str) -> Instance:
        """Parse a map file from disk using a context manager."""
        with open(path, encoding="utf-8") as handle:
            return self.parse(handle.read())

    @staticmethod
    def _strip_comment(line: str) -> str:
        """Remove everything from the first '#' character."""
        position = line.find("#")
        return line if position < 0 else line[:position]

    @staticmethod
    def _parse_nb_drones(line: str, line_no: int) -> int:
        """Parse the mandatory first content line."""
        match = _DRONE_PATTERN.match(line)
        if match is None:
            if ":" not in line:
                raise ParseError(
                    "first line must be 'nb_drones: <n>'", line_no
                )
            if not line.startswith("nb_drones:"):
                raise ParseError(
                    f"unknown directive '{line}' before nb_drones", line_no
                )
            raise ParseError("invalid drone count", line_no)
        value = int(match.group(1))
        if value < 1:
            raise ParseError("drone count must be a positive integer", line_no)
        return value

    @staticmethod
    def _parse_zone(line: str, line_no: int) -> Zone:
        """Parse a hub definition line into a Zone."""
        match = _ZONE_PATTERN.match(line)
        if match is None:
            raise ParseError(f"malformed zone definition '{line}'", line_no)
        kind, name, x_raw, y_raw, metadata = match.groups()
        if "-" in name or " " in name:
            raise ParseError(
                f"invalid zone name '{name}' (no dashes or spaces)", line_no
            )
        tags = Parser._parse_metadata(metadata, _VALID_ZONE_KEYS, line_no)
        zone_type = ZoneType.NORMAL
        if "zone" in tags:
            if tags["zone"] not in _ZONE_TYPES:
                raise ParseError(
                    f"invalid zone type '{tags['zone']}'", line_no
                )
            zone_type = ZoneType(tags["zone"])
        max_drones: int | None = None
        if "max_drones" in tags:
            max_drones = Parser._positive_int(
                tags["max_drones"], "max_drones", line_no
            )
        is_start = kind == "start_hub"
        is_end = kind == "end_hub"
        return Zone(
            name=name,
            x=int(x_raw),
            y=int(y_raw),
            zone_type=zone_type,
            color=tags.get("color"),
            max_drones=max_drones,
            is_start=is_start,
            is_end=is_end,
        )

    @staticmethod
    def _parse_connection(line: str, line_no: int) -> Connection:
        """Parse a connection line: 'connection: a-b [metadata]'."""
        match = _CONNECTION_PATTERN.match(line)
        if match is None:
            raise ParseError(
                f"malformed connection definition '{line}'", line_no
            )
        pair, metadata = match.groups()
        parts = pair.split("-")
        if len(parts) != 2 or not all(parts):
            raise ParseError(
                f"invalid connection '{pair}' (expected zone1-zone2)", line_no
            )
        tags = Parser._parse_metadata(
            metadata, _VALID_LINK_KEYS, line_no
        )
        capacity: int | None = None
        if "max_link_capacity" in tags:
            capacity = Parser._positive_int(
                tags["max_link_capacity"], "max_link_capacity", line_no
            )
        return Connection(parts[0], parts[1], capacity)

    @staticmethod
    def _parse_metadata(
        metadata: str | None,
        valid_keys: tuple[str, ...],
        line_no: int,
    ) -> dict[str, str]:
        """Parse a bracketed '[key=value ...]' metadata block."""
        if not metadata:
            return {}
        inner = metadata[1:-1].strip()
        if not inner:
            return {}
        tags: dict[str, str] = {}
        for tag in inner.split():
            if "=" not in tag:
                raise ParseError(
                    f"malformed metadata tag '{tag}' "
                    "(expected key=value)",
                    line_no,
                )
            key, value = tag.split("=", 1)
            if key not in valid_keys:
                raise ParseError(f"unknown metadata key '{key}'", line_no)
            if key in tags:
                raise ParseError(f"duplicate metadata key '{key}'", line_no)
            if not value:
                raise ParseError(f"empty value for '{key}'", line_no)
            tags[key] = value
        return tags

    @staticmethod
    def _positive_int(value: str, key: str, line_no: int) -> int:
        """Convert a capacity value, requiring a positive integer."""
        if not value.isdigit():
            raise ParseError(
                f"{key} must be a positive integer, got '{value}'", line_no
            )
        number = int(value)
        if number < 1:
            raise ParseError(f"{key} must be positive", line_no)
        return number
