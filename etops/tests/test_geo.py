import math

import pytest

from etops.geo import EARTH_RADIUS_NM, destination_point, haversine

GANDER = (48.9369, -54.5681)
STILL_AIR_RADIUS_NM = 1290.0  # 430 kt * 180 min / 60
BEARINGS = list(range(0, 360, 5))


def test_seventy_two_bearings():
    assert len(BEARINGS) == 72


@pytest.mark.parametrize("bearing", BEARINGS)
def test_destination_round_trips_to_1290nm(bearing):
    lat, lon = destination_point(*GANDER, bearing, STILL_AIR_RADIUS_NM)
    assert haversine(*GANDER, lat, lon) == pytest.approx(STILL_AIR_RADIUS_NM, abs=0.01)


def test_haversine_zero_distance():
    assert haversine(*GANDER, *GANDER) == 0.0


def test_bearing_convention_clockwise_from_north():
    lat0, lon0 = GANDER
    n_lat, n_lon = destination_point(lat0, lon0, 0, 300)
    e_lat, e_lon = destination_point(lat0, lon0, 90, 300)
    s_lat, s_lon = destination_point(lat0, lon0, 180, 300)
    w_lat, w_lon = destination_point(lat0, lon0, 270, 300)

    assert n_lat > lat0 and n_lon == pytest.approx(lon0)
    assert s_lat < lat0 and s_lon == pytest.approx(lon0)
    assert e_lon > lon0
    assert w_lon < lon0


def test_longitude_wraps_across_antimeridian():
    distance_nm = 120
    lat, lon = destination_point(0.0, 179.0, 90, distance_nm)
    expected_lon = 179.0 + math.degrees(distance_nm / EARTH_RADIUS_NM) - 360.0
    assert -180.0 <= lon < 180.0
    assert lat == pytest.approx(0.0, abs=1e-9)
    assert lon == pytest.approx(expected_lon, abs=1e-9)
