"""Tests of the headless (pure) graphical renderer."""

from __future__ import annotations

from conftest import map_path, solve_map
from gui import GuiRenderer, ZonePalette
from parser import Parser

import sample_maps


def test_renderer_positions_cover_all_zones() -> None:
    instance = Parser().parse(sample_maps.LINEAR_MAP)
    renderer = GuiRenderer(instance)
    assert set(renderer.positions) == set(instance.network.zones)
    ys = {y for _, y in renderer.positions.values()}
    assert len(ys) == 1


def test_renderer_links_follow_connections() -> None:
    instance = Parser().parse(sample_maps.LINEAR_MAP)
    renderer = GuiRenderer(instance)
    assert len(renderer.links) == len(instance.network.connections)


def test_renderer_icons_and_fills() -> None:
    instance = Parser().parse(sample_maps.RESTRICTED_MAP)
    renderer = GuiRenderer(instance)
    assert renderer.icon_of("start") == "[S]"
    assert renderer.icon_of("end") == "[E]"
    assert renderer.icon_of("lab") == "[!]"
    assert renderer.icon_of("b") == "[ ]"


def test_palette_resolves_names_and_fallback() -> None:
    palette = ZonePalette()
    assert palette.resolve("red") == (231, 76, 60)
    assert palette.resolve(None) is None
    weird = palette.resolve("plaid")
    assert weird is not None
    assert weird == palette.resolve("plaid")


def test_replay_states_follow_the_result() -> None:
    instance = Parser().parse(sample_maps.LINEAR_MAP)
    renderer = GuiRenderer(instance)
    result = solve_map("easy_1.map")
    states = renderer.replay_states(result)
    assert len(states) == result.total_turns + 1
    assert all(name == instance.start for name in states[0].values())
    assert all(name == instance.end for name in states[-1].values())


def test_drone_spots_spread_busy_zones() -> None:
    instance = Parser().parse(sample_maps.LINEAR_MAP)
    renderer = GuiRenderer(instance)
    spots = renderer.drone_spots({1: "a", 2: "a"})
    assert spots[1] != spots[2]
    single = renderer.drone_spots({1: "a"})
    assert single[1] == renderer.positions["a"]


def test_congested_map_has_a_canvas() -> None:
    instance = Parser().parse_file(map_path("medium_1.map"))
    renderer = GuiRenderer(instance)
    width, height = renderer.canvas_size()
    assert width > 0 and height > 0
