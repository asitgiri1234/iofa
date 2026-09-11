import logging
from datetime import datetime, timezone

import pytest

from etops.loaders import parse_timestamp
from etops.wind import WindField

GANDER = (48.9369, -54.5681)


@pytest.fixture(scope="module")
def field():
    return WindField.from_file()


def test_has_five_snapshots(field):
    assert len(field.snapshots) == 5


# --- worked_example.pdf ---------------------------------------------------

def test_worked_example_picks_0600_snapshot(field):
    snap = field.nearest_snapshot("2026-07-25T05:00:00Z")
    assert snap.timestamp == parse_timestamp("2026-07-25T06:00:00Z")


def test_worked_example_nearest_grid_point(field):
    snap = field.nearest_snapshot("2026-07-25T05:00:00Z")
    p = field.nearest_grid_point(snap, *GANDER)
    assert (p.lat, p.lon, p.u, p.v) == (49.0, -54.0, 32.0, -2.4)


def test_worked_example_wind_at(field):
    assert field.wind_at(*GANDER, "2026-07-25T05:00:00Z") == (32.0, -2.4)


def test_all_snapshots_give_different_u_at_gander(field):
    us = [field.wind_at(*GANDER, s.timestamp)[0] for s in field.snapshots]
    assert len(set(us)) == 5
    assert us == [28.7, 32.0, 36.1, 40.4, 44.0]  # worked example, step 4


# --- time selection -------------------------------------------------------

def test_tie_breaks_to_earlier_snapshot(field):
    # 03:00Z is exactly halfway between 00:00Z and 06:00Z.
    snap = field.nearest_snapshot("2026-07-25T03:00:00Z")
    assert snap.timestamp == parse_timestamp("2026-07-25T00:00:00Z")


def test_just_past_midpoint_goes_to_later_snapshot(field):
    snap = field.nearest_snapshot("2026-07-25T03:00:01Z")
    assert snap.timestamp == parse_timestamp("2026-07-25T06:00:00Z")


def test_times_outside_range_use_first_and_last(field):
    assert field.nearest_snapshot("2026-07-24T12:00:00Z") is field.snapshots[0]
    assert field.nearest_snapshot("2026-07-27T00:00:00Z") is field.snapshots[-1]


def test_accepts_aware_datetime(field):
    when = datetime(2026, 7, 25, 5, tzinfo=timezone.utc)
    assert field.wind_at(*GANDER, when) == (32.0, -2.4)


def test_rejects_naive_datetime(field):
    with pytest.raises(ValueError):
        field.nearest_snapshot(datetime(2026, 7, 25, 5))


# --- spatial clamping -----------------------------------------------------

def test_inside_grid_does_not_warn(field, caplog):
    with caplog.at_level(logging.WARNING, logger="etops.wind"):
        field.wind_at(*GANDER, "2026-07-25T05:00:00Z")
    assert not caplog.records


def test_outside_grid_clamps_to_edge_and_warns(field, caplog):
    # MSY origin (29.99, -90.26) is south-west of the grid -> corner cell (35, -60).
    with caplog.at_level(logging.WARNING, logger="etops.wind"):
        u, v = field.wind_at(29.99, -90.26, "2026-07-25T00:00:00Z")
    assert (u, v) == (11.3, -4.3)
    assert any("outside the wind grid" in r.getMessage() for r in caplog.records)


def test_outside_grid_clamps_along_one_axis(field):
    # Due east of the grid at lat 49 -> edge cell (49, -10) in the 00:00Z snapshot.
    assert field.wind_at(49.0, 2.5479, "2026-07-25T00:00:00Z") == (35.1, -0.9)
