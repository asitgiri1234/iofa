import json

import pytest
from shapely.geometry import Polygon

from etops.coverage import check_route, load_ring_polygons
from etops.geo import haversine
from etops.loaders import (
    Route,
    Waypoint,
    load_aircraft,
    load_airports,
    load_route,
    parse_timestamp,
)
from etops.rings import build_all_rings
from etops.wind import WindField


@pytest.fixture(scope="module")
def airports():
    return load_airports()


@pytest.fixture(scope="module")
def field():
    return WindField.from_file()


@pytest.fixture(scope="module")
def route():
    return load_route()


@pytest.fixture(scope="module")
def rings(airports, field):
    return load_ring_polygons(build_all_rings(airports, load_aircraft(), field))


@pytest.fixture(scope="module")
def report(route, rings, field, airports):
    return check_route(route, rings, field, airports)


def one_waypoint_route(lat, lon, eta):
    return Route("X", "Y", parse_timestamp(eta), 480.0, [Waypoint(lat, lon, parse_timestamp(eta))])


# --- sample route: expected result ---------------------------------------

def test_first_waypoint_is_not_covered(report):
    first = report["waypoints"][0]
    assert (first["lat"], first["lon"]) == (29.99, -90.26)
    assert first["covered"] is False
    assert first["covering_airports"] == []


def test_sample_route_is_not_fully_covered(report):
    assert report["fully_covered"] is False
    assert report["gap_count"] >= 1


def test_gap_count_matches_uncovered_waypoints(report):
    assert report["gap_count"] == sum(not w["covered"] for w in report["waypoints"])


def test_report_shape(report, route):
    assert set(report) == {"waypoints", "fully_covered", "gap_count"}
    assert len(report["waypoints"]) == len(route.waypoints)
    for w in report["waypoints"]:
        assert {"lat", "lon", "eta", "snapshot_used", "covered",
                "covering_airports", "nearest_airport_nm"} <= set(w)
    json.dumps(report)  # must be serialisable as-is


def test_snapshot_used_per_waypoint(report):
    # etas run 00:00Z..08:59Z; 03:00Z is the 00Z/06Z midpoint, 09:00Z the 06Z/12Z one.
    used = [w["snapshot_used"] for w in report["waypoints"]]
    assert used == ["2026-07-25T00:00:00Z"] * 2 + ["2026-07-25T06:00:00Z"] * 7


def test_nearest_airport_nm(report, airports):
    first = report["waypoints"][0]
    expected = min(haversine(29.99, -90.26, a.lat, a.lon) for a in airports)
    assert first["nearest_airport_nm"] == pytest.approx(expected, abs=0.01)
    assert first["nearest_airport_nm"] > 1500  # well beyond any ring


# --- time handling --------------------------------------------------------

def test_airport_itself_is_covered_by_its_own_ring(rings, field, airports):
    r = check_route(one_waypoint_route(48.9369, -54.5681, "2026-07-25T05:00:00Z"), rings, field, airports)
    wp = r["waypoints"][0]
    assert wp["covered"] and "CYQX" in wp["covering_airports"]
    assert wp["snapshot_used"] == "2026-07-25T06:00:00Z"
    assert wp["nearest_airport"] == "CYQX" and wp["nearest_airport_nm"] == 0.0


def test_eta_tie_uses_earlier_snapshot(rings, field, airports):
    r = check_route(one_waypoint_route(45.0, -45.0, "2026-07-25T03:00:00Z"), rings, field, airports)
    assert r["waypoints"][0]["snapshot_used"] == "2026-07-25T00:00:00Z"


def test_only_the_nearest_snapshot_rings_are_used(field, airports):
    t00 = parse_timestamp("2026-07-25T00:00:00Z")
    t12 = parse_timestamp("2026-07-25T12:00:00Z")
    everywhere = Polygon([(-179, -89), (179, -89), (179, 89), (-179, 89)])
    nowhere = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    rings = {("AAAA", t00): nowhere, ("AAAA", t12): everywhere}

    at_00 = check_route(one_waypoint_route(45.0, -45.0, "2026-07-25T00:30:00Z"), rings, field, airports)
    at_12 = check_route(one_waypoint_route(45.0, -45.0, "2026-07-25T11:30:00Z"), rings, field, airports)
    assert at_00["waypoints"][0]["covered"] is False  # the 12Z ring must not leak in
    assert at_12["waypoints"][0]["covered"] is True


def test_missing_snapshot_rings_raise(field, airports):
    rings = {("AAAA", parse_timestamp("2026-07-25T12:00:00Z")): Polygon([(0, 0), (1, 0), (1, 1)])}
    with pytest.raises(ValueError):
        check_route(one_waypoint_route(45.0, -45.0, "2026-07-25T00:00:00Z"), rings, field, airports)


# --- ring loading ---------------------------------------------------------

def test_loads_25_polygons_keyed_by_icao_and_timestamp(rings, airports, field):
    assert len(rings) == 25
    assert set(rings) == {(a.icao, s.timestamp) for a in airports for s in field.snapshots}
    assert all(p.is_valid for p in rings.values())


def test_load_from_geojson_file(tmp_path, airports, field):
    fc = build_all_rings(airports, load_aircraft(), field)
    path = tmp_path / "rings.geojson"
    path.write_text(json.dumps(fc), encoding="utf-8")
    assert len(load_ring_polygons(path)) == 25
