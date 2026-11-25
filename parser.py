"""Parser for the Fly-in map format.

The format is line based:

    nb_drones: <n>
    start_hub: <name> <x> <y> [k=v ...]
    end_hub: <name> <x> <y> [k=v ...]
    hub: <name> <x> <y> [k=v ...]
    connection: <name1>-<name2> [k=v ...]

Comments start with '#' and blank lines are ignored. Any invalid input
raises a ParseError carrying the offending line number. The parser is
written from scratch: manual character splitting replaces regular
expressions.
"""

from __future__ import annotations

from connection import Connection
from errors import ParseError
from instance import Instance
from network import Network
from zone import Zone, zone_type_from_name

_ZONE_DIRECTIVES = ("start_hub", "end_hub", "hub")
_VALID_ZONE_KEYS = ("zone", "color", "max_drones")
_VALID_LINK_KEYS = ("max_link_capacity",)


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
            directive = self._directive_of(line, line_no)
            if directive in _ZONE_DIRECTIVES:
                zone = self._parse_zone(line, directive, line_no)
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
            elif directive == "connection":
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
    def _directive_of(line: str, line_no: int) -> str:
        """Return the directive word written before the first colon."""
        colon = line.find(":")
        if colon <= 0:
            raise ParseError(f"unknown directive '{line}'", line_no)
        return line[:colon]

    @staticmethod
    def _integer(text: str, what: str, line_no: int) -> int:
        """Parse a plain signed integer, manually."""
        digits = text[1:] if text[:1] in ("-", "+") else text
        if not digits or not digits.isdigit():
            raise ParseError(
                f"invalid {what} '{text}' (expected an integer)", line_no
            )
        value = int(digits)
        if text[:1] == "-":
            value = -value
        return value

    @staticmethod
    def _split_metadata(
        line: str, line_no: int
    ) -> tuple[str, str | None]:
        """Split a '[key=value ...]' suffix from a line remainder.

        Returns the text before the bracket and the raw metadata, or
        None when there is no metadata at all.
        """
        opener = line.find("[")
        if opener < 0:
            return line.strip(), None
        closer = line.find("]", opener + 1)
        if closer < 0:
            raise ParseError("unterminated metadata block", line_no)
        trailing = line[closer + 1:].strip()
        if trailing:
            raise ParseError(
                f"unexpected text after metadata '{trailing}'", line_no
            )
        head = line[:opener]
        if head and not head.endswith(" "):
            raise ParseError(
                f"metadata must follow a space '{line.strip()}'", line_no
            )
        return head, line[opener + 1:closer]

    @staticmethod
    def _parse_nb_drones(line: str, line_no: int) -> int:
        """Parse the mandatory first content line."""
        if not line.startswith("nb_drones:"):
            if ":" in line:
                raise ParseError(
                    f"unknown directive '{line}' before nb_drones", line_no
                )
            raise ParseError(
                "first line must be 'nb_drones: <n>'", line_no
            )
        value = Parser._integer(line[10:].strip(), "drone count", line_no)
        if value < 1:
            raise ParseError(
                "drone count must be a positive integer", line_no
            )
        return value

    @staticmethod
    def _parse_zone(line: str, directive: str, line_no: int) -> Zone:
        """Parse a hub definition line into a Zone."""
        remainder = line[len(directive) + 1:]
        head, metadata = Parser._split_metadata(remainder, line_no)
        fields = head.split()
        if len(fields) != 3:
            raise ParseError(
                f"malformed zone definition '{line}' "
                "(expected 'name x y')",
                line_no,
            )
        name = fields[0]
        if "-" in name:
            raise ParseError(
                f"invalid zone name '{name}' (no dashes or spaces)", line_no
            )
        tags = Parser._parse_metadata(metadata, _VALID_ZONE_KEYS, line_no)
        default_type = zone_type_from_name("normal")
        if default_type is None:
            raise ParseError("'normal' zone type is not registered", line_no)
        zone_type = default_type
        if "zone" in tags:
            candidate = zone_type_from_name(tags["zone"])
            if candidate is None:
                raise ParseError(
                    f"invalid zone type '{tags['zone']}'", line_no
                )
            zone_type = candidate
        max_drones: int | None = None
        if "max_drones" in tags:
            max_drones = Parser._positive_int(
                tags["max_drones"], "max_drones", line_no
            )
        return Zone(
            name=name,
            x=Parser._integer(fields[1], "x coordinate", line_no),
            y=Parser._integer(fields[2], "y coordinate", line_no),
            zone_type=zone_type,
            color=tags.get("color"),
            max_drones=max_drones,
            is_start=directive == "start_hub",
            is_end=directive == "end_hub",
        )

    @staticmethod
    def _parse_connection(line: str, line_no: int) -> Connection:
        """Parse a connection line: 'connection: a-b [metadata]'."""
        remainder = line[len("connection") + 1:]
        head, metadata = Parser._split_metadata(remainder, line_no)
        fields = head.split()
        if len(fields) != 1:
            raise ParseError(
                f"malformed connection definition '{line}'", line_no
            )
        pair = fields[0]
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
        inner = metadata.strip()
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
