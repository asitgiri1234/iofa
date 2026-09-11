import re

import folium
import pytest

from etops.loaders import load_aircraft, load_airports, load_route
from etops.mapping import _ranges, build_coverage_map
from etops.pipeline import run_pipeline
from etops.wind import WindField


@pytest.fixture(scope="module")
def airports():
    return load_airports()


@pytest.fixture(scope="module")
def result(airports):
    return run_pipeline(airports, load_aircraft(), load_route(), WindField.from_file())


@pytest.fixture(scope="module")
def html(result, airports):
    rings, report = result
    return build_coverage_map(rings, report, airports).get_root().render()


def test_ranges():
    assert _ranges([1, 2]) == "1-2"
    assert _ranges([3, 4, 5, 6, 7, 8, 9]) == "3-9"
    assert _ranges([1, 3, 4, 7]) == "1, 3-4, 7"


def test_returns_folium_map(result, airports):
    rings, report = result
    assert isinstance(build_coverage_map(rings, report, airports), folium.Map)


def test_default_shows_only_snapshots_used_by_waypoints(html):
    # Sample route uses 00Z (WP 1-2) and 06Z (WP 3-9) only.
    assert "Rings @ 2026-07-25 00:00Z (WP 1-2)" in html
    assert "Rings @ 2026-07-25 06:00Z (WP 3-9)" in html
    for unused in ("12:00Z", "18:00Z", "2026-07-26 00:00Z"):
        assert f"Rings @ {unused}" not in html and f"ring @ 2026-07-25 {unused}" not in html


def test_ten_rings_drawn_by_default(html):
    # 2 used snapshots x 5 airports
    assert html.count(" ring @ ") == 10


def test_waypoints_coloured_by_coverage(html, result):
    _, report = result
    n_gap = sum(not w["covered"] for w in report["waypoints"])
    assert html.count(": GAP — ") == n_gap == 1
    assert html.count(": covered — ") == len(report["waypoints"]) - n_gap


def test_waypoints_drawn_in_their_own_pane_above_rings(html, result):
    _, report = result
    assert '"waypoints"' in html and "zIndex = 640" in html
    assert len(re.findall(r'"pane":\s*"waypoints"', html)) == len(report["waypoints"])


def test_popup_contents(html):
    assert "Snapshot used: 2026-07-25T00:00:00Z" in html
    assert "Covered by: none" in html
    assert "Covered by: BIKF, CYQX, CYYT, EINN, LPLA" in html


def test_layers_legend_and_airports(html, airports):
    assert "L.control.layers" in html
    assert "Rings by wind snapshot" in html  # legend
    assert "Not fully covered" in html
    for a in airports:
        assert f"{a.icao} — {a.name}" in html


def test_explicit_snapshot_selection(result, airports):
    rings, report = result
    html = build_coverage_map(rings, report, airports, snapshots=["2026-07-25T18:00:00Z"]).get_root().render()
    assert "Rings @ 2026-07-25 18:00Z (no waypoints)" in html
    assert html.count(" ring @ ") == 5


def test_unknown_snapshot_raises(result, airports):
    rings, report = result
    with pytest.raises(ValueError):
        build_coverage_map(rings, report, airports, snapshots=["2030-01-01T00:00:00Z"])
