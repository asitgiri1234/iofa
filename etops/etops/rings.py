"""Wind-adjusted diversion rings ("egg shapes"), one per (airport, wind snapshot)."""

from __future__ import annotations

import math
from datetime import datetime

from etops.geo import destination_point
from etops.loaders import Aircraft, Airport, format_timestamp
from etops.wind import WindField

BEARINGS_DEG = tuple(range(0, 360, 5))  # 72 directions, clockwise from true north


def reach_distance_nm(bearing_deg: float, u: float, v: float, aircraft: Aircraft) -> float:
    """Distance reachable along ``bearing_deg`` within the rating time, given wind (u, v)."""
    b = math.radians(bearing_deg)
    wind_component = u * math.sin(b) + v * math.cos(b)  # + tailwind, - headwind
    groundspeed = aircraft.diversion_speed_kt + wind_component
    # A headwind stronger than the aircraft's airspeed means no progress, not negative
    # distance (which would flip the point to the opposite side of the airport).
    return max(0.0, groundspeed) * (aircraft.rating_minutes / 60)


def build_ring(
    airport: Airport,
    snapshot_time: datetime | str,
    aircraft: Aircraft,
    wind_field: WindField,
) -> list[tuple[float, float]]:
    """72 (lat, lon) ring points in bearing order, closed by repeating the first point.

    Wind is looked up once, at the airport, and applied to every bearing.
    """
    u, v = wind_field.wind_at(airport.lat, airport.lon, snapshot_time)
    return _ring_for_wind(airport, u, v, aircraft)


def _ring_for_wind(airport: Airport, u: float, v: float, aircraft: Aircraft) -> list[tuple[float, float]]:
    points = [
        destination_point(airport.lat, airport.lon, b, reach_distance_nm(b, u, v, aircraft))
        for b in BEARINGS_DEG
    ]
    points.append(points[0])
    return points


def ring_feature(
    airport: Airport,
    snapshot_time: datetime,
    aircraft: Aircraft,
    wind_field: WindField,
) -> dict:
    """GeoJSON Polygon feature for one (airport, snapshot)."""
    u, v = wind_field.wind_at(airport.lat, airport.lon, snapshot_time)
    ring = _ring_for_wind(airport, u, v, aircraft)
    # Bearings sweep clockwise; RFC 7946 wants exterior rings counter-clockwise.
    # Reversing a closed ring keeps the bearing-0 point first and last.
    coordinates = [[lon, lat] for lat, lon in reversed(ring)]
    return {
        "type": "Feature",
        "properties": {
            "icao": airport.icao,
            "aircraft": aircraft.aircraft,
            "timestamp": format_timestamp(snapshot_time),
            "wind_u_kt": u,
            "wind_v_kt": v,
        },
        "geometry": {"type": "Polygon", "coordinates": [coordinates]},
    }


def build_all_rings(airports: list[Airport], aircraft: Aircraft, wind_field: WindField) -> dict:
    """FeatureCollection with one ring per (airport, snapshot)."""
    return {
        "type": "FeatureCollection",
        "features": [
            ring_feature(airport, snapshot.timestamp, aircraft, wind_field)
            for airport in airports
            for snapshot in wind_field.snapshots
        ],
    }
