"""Parser and validation tests."""

from __future__ import annotations

import os

import pytest

from errors import ParseError
from parser import Parser
from conftest import map_path
from zone import ZoneType

from sample_maps import RESTRICTED_MAP, LINEAR_MAP


def test_parse_basic_instance(parser: Parser) -> None:
    instance = parser.parse(LINEAR_MAP)
    assert instance.nb_drones == 2
    assert instance.start == "start"
    assert instance.end == "end"
    assert len(instance.network.zones) == 4
    assert len(instance.network.connections) == 3


def test_zone_types_and_defaults(parser: Parser) -> None:
    instance = parser.parse(RESTRICTED_MAP)
    lab = instance.network.get_zone("lab")
    assert lab.zone_type is ZoneType.RESTRICTED
    assert lab.entry_cost == 2
    assert lab.capacity == 1
    default = instance.network.get_zone("b")
    assert default.zone_type is ZoneType.NORMAL
    assert default.color is None


def test_hub_capacities_are_ignored(parser: Parser) -> None:
    content = RESTRICTED_MAP.replace(
        "end_hub: end 3 0", "end_hub: end 3 0 [max_drones=3 color=red]"
    )
    instance = parser.parse(content)
    assert instance.end_zone.capacity is None


def test_first_line_must_be_nb_drones(parser: Parser) -> None:
    with pytest.raises(ParseError) as error:
        parser.parse("hub: a 0 0\n")
    assert error.value.line_no == 1


def test_negative_drone_count(parser: Parser) -> None:
    with pytest.raises(ParseError):
        parser.parse("nb_drones: -2\n")


def test_zero_drone_count(parser: Parser) -> None:
    with pytest.raises(ParseError):
        parser.parse("nb_drones: 0\n")


def test_duplicate_start_hub(parser: Parser) -> None:
    content = LINEAR_MAP + "start_hub: other 9 9\n"
    with pytest.raises(ParseError) as error:
        parser.parse(content)
    assert error.value.line_no == LINEAR_MAP.count(chr(10)) + 1


def test_missing_start_hub(parser: Parser) -> None:
    content = LINEAR_MAP.replace("start_hub: start 0 0\n", "")
    with pytest.raises(ParseError):
        parser.parse(content)


def test_missing_end_hub(parser: Parser) -> None:
    content = LINEAR_MAP.replace(
        "end_hub: end 3 0\n", "hub: end 3 0\n"
    )
    with pytest.raises(ParseError):
        parser.parse(content)


def test_duplicate_zone_name(parser: Parser) -> None:
    content = LINEAR_MAP + "hub: a 5 5\n"
    with pytest.raises(ParseError) as error:
        parser.parse(content)
    assert error.value.line_no == LINEAR_MAP.count(chr(10)) + 1


def test_dash_in_zone_name(parser: Parser) -> None:
    with pytest.raises(ParseError):
        parser.parse(LINEAR_MAP.replace("hub: a 1 0", "hub: a-b 1 0"))


def test_non_integer_coordinates(parser: Parser) -> None:
    with pytest.raises(ParseError):
        parser.parse(LINEAR_MAP.replace("hub: a 1 0", "hub: a 1.5 0"))


def test_unknown_zone_type(parser: Parser) -> None:
    with pytest.raises(ParseError) as error:
        parser.parse(
            LINEAR_MAP.replace("hub: a 1 0", "hub: a 1 0 [zone=weird]")
        )
    assert "zone type" in str(error.value)


def test_invalid_capacity(parser: Parser) -> None:
    for bad in ("max_drones=0", "max_drones=-1", "max_drones=x"):
        content = LINEAR_MAP.replace(
            "hub: a 1 0", f"hub: a 1 0 [{bad}]"
        )
        with pytest.raises(ParseError):
            parser.parse(content)


def test_unknown_metadata_key(parser: Parser) -> None:
    with pytest.raises(ParseError):
        parser.parse(LINEAR_MAP.replace("hub: a 1 0", "hub: a 1 0 [foo=1]"))


def test_malformed_metadata(parser: Parser) -> None:
    with pytest.raises(ParseError):
        parser.parse(LINEAR_MAP.replace("hub: a 1 0", "hub: a 1 0 [zone]"))


def test_connection_to_unknown_zone(parser: Parser) -> None:
    content = LINEAR_MAP + "connection: a-nowhere\n"
    with pytest.raises(ParseError) as error:
        parser.parse(content)
    assert error.value.line_no == LINEAR_MAP.count(chr(10)) + 1


def test_duplicate_connection_reversed_order(parser: Parser) -> None:
    content = LINEAR_MAP + "connection: b-a\n"
    with pytest.raises(ParseError):
        parser.parse(content)


def test_self_connection(parser: Parser) -> None:
    content = LINEAR_MAP + "connection: a-a\n"
    with pytest.raises(ParseError):
        parser.parse(content)


def test_connection_missing_dash(parser: Parser) -> None:
    with pytest.raises(ParseError):
        parser.parse(
            LINEAR_MAP.replace("connection: start-a", "connection: start a")
        )


def test_unknown_directive(parser: Parser) -> None:
    with pytest.raises(ParseError):
        parser.parse(LINEAR_MAP + "tunnel: x\n")


def test_comments_and_blank_lines(parser: Parser) -> None:
    content = "# header\n\n" + LINEAR_MAP + "# tail comment\n"
    instance = parser.parse(content)
    assert instance.nb_drones == 2


def test_invalid_link_capacity(parser: Parser) -> None:
    content = LINEAR_MAP.replace(
        "connection: b-end", "connection: b-end [max_link_capacity=0]"
    )
    with pytest.raises(ParseError):
        parser.parse(content)


def test_empty_file(parser: Parser) -> None:
    with pytest.raises(ParseError):
        parser.parse("\n# only comments\n")


def test_bundled_maps_are_valid(parser: Parser) -> None:
    for name in sorted(os.listdir(map_path("."))):
        if not name.endswith(".map"):
            continue
        instance = parser.parse_file(map_path(name))
        instance.validate_topology()
