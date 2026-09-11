import math

import pytest

from etops.geo import haversine
from etops.loaders import WindPoint, WindSnapshot, load_aircraft, load_airports, parse_timestamp
from etops.rings import BEARINGS_DEG, build_all_rings, build_ring, reach_distance_nm
from etops.wind import WindField

T0600 = "2026-07-25T06:00:00Z"


@pytest.fixture(scope="module")
def airports():
    return load_airports()


@pytest.fixture(scope="module")
def gander(airports):
    return next(a for a in airports if a.icao == "CYQX")


@pytest.fixture(scope="module")
def aircraft():
    return load_aircraft()


@pytest.fixture(scope="module")
def field():
    return WindField.from_file()


@pytest.fixture(scope="module")
def collection(airports, aircraft, field):
    return build_all_rings(airports, aircraft, field)


def distance_at(ring, airport, bearing):
    lat, lon = ring[BEARINGS_DEG.index(bearing)]
    return haversine(airport.lat, airport.lon, lat, lon)


# --- worked_example.pdf, step 3 ------------------------------------------

@pytest.mark.parametrize(
    "bearing, expected_nm",
    [(0, 1282.80), (90, 1386.00), (180, 1297.20), (270, 1194.00)],
)
def test_gander_0600_cardinal_distances(gander, aircraft, field, bearing, expected_nm):
    ring = build_ring(gander, T0600, aircraft, field)
    assert distance_at(ring, gander, bearing) == pytest.approx(expected_nm, abs=0.01)


def test_egg_points_downwind(gander, aircraft, field):
    # Wind at Gander 06Z (u=32, v=-2.4) blows toward bearing atan2(32, -2.4) ~ 94.3 deg,
    # so the ring bulges at the 5-degree step nearest that (95) and pinches opposite (275).
    ring = build_ring(gander, T0600, aircraft, field)
    dists = {b: distance_at(ring, gander, b) for b in BEARINGS_DEG}
    downwind = math.degrees(math.atan2(32.0, -2.4)) % 360
    assert downwind == pytest.approx(94.29, abs=0.01)
    assert max(dists, key=dists.get) == 95
    assert min(dists, key=dists.get) == 275
    assert dists[90] > dists[270]  # east sticks out, west pinches in


# --- ring structure -------------------------------------------------------

def test_build_ring_has_73_points_closed(gander, aircraft, field):
    ring = build_ring(gander, T0600, aircraft, field)
    assert len(ring) == 73
    assert ring[0] == ring[-1]


def test_every_ring_has_73_points_closed(collection):
    for feature in collection["features"]:
        coords = feature["geometry"]["coordinates"][0]
        assert len(coords) == 73
        assert coords[0] == coords[-1]


def test_still_air_is_a_circle(gander, aircraft):
    calm = WindField([WindSnapshot(parse_timestamp(T0600), [WindPoint(49.0, -54.0, 0.0, 0.0)])])
    ring = build_ring(gander, T0600, aircraft, calm)
    for bearing in BEARINGS_DEG:
        assert distance_at(ring, gander, bearing) == pytest.approx(1290.0, abs=0.01)


def test_headwind_stronger_than_airspeed_gives_zero_not_negative(aircraft):
    assert reach_distance_nm(270, u=500.0, v=0.0, aircraft=aircraft) == 0.0


def test_rings_differ_across_snapshots(gander, aircraft, field):
    rings = [build_ring(gander, s.timestamp, aircraft, field) for s in field.snapshots]
    east = [distance_at(r, gander, 90) for r in rings]
    assert east == pytest.approx([1376.10, 1386.00, 1398.30, 1411.20, 1422.00], abs=0.01)


# --- GeoJSON --------------------------------------------------------------

def test_feature_collection_has_25_features(collection):
    assert collection["type"] == "FeatureCollection"
    assert len(collection["features"]) == 25
    pairs = {(f["properties"]["icao"], f["properties"]["timestamp"]) for f in collection["features"]}
    assert len(pairs) == 25


def test_feature_properties(collection):
    f = next(
        f for f in collection["features"]
        if f["properties"]["icao"] == "CYQX" and f["properties"]["timestamp"] == T0600
    )
    assert f["type"] == "Feature"
    assert f["geometry"]["type"] == "Polygon"
    assert f["properties"]["aircraft"] == "B789"
    assert (f["properties"]["wind_u_kt"], f["properties"]["wind_v_kt"]) == (32.0, -2.4)


def test_coordinates_are_lon_lat(collection, gander):
    f = next(f for f in collection["features"] if f["properties"]["icao"] == "CYQX")
    first_lon, first_lat = f["geometry"]["coordinates"][0][0]
    # First point is the bearing-0 (due north) point: same longitude, higher latitude.
    assert first_lon == pytest.approx(gander.lon)
    assert first_lat > gander.lat + 20


def test_exterior_rings_are_counter_clockwise(collection):
    # RFC 7946 right-hand rule; positive shoelace area in (lon, lat) means CCW.
    for feature in collection["features"]:
        coords = feature["geometry"]["coordinates"][0]
        area2 = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(coords, coords[1:]))
        assert area2 > 0
