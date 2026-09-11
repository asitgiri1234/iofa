"""Time-aware route coverage: is each waypoint inside a ring from its own snapshot?"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from shapely.geometry import Point, Polygon

from etops.geo import haversine
from etops.loaders import Airport, Route, format_timestamp, parse_timestamp
from etops.wind import WindField

RingKey = tuple[str, datetime]  # (icao, snapshot timestamp)


def load_ring_polygons(source: dict | Path | str) -> dict[RingKey, Polygon]:
    """Ring polygons keyed by (icao, timestamp), from a FeatureCollection dict or a
    path to rings.geojson. Polygons stay in GeoJSON's (lon, lat) axis order.
    """
    if not isinstance(source, dict):
        source = json.loads(Path(source).read_text(encoding="utf-8"))

    polygons: dict[RingKey, Polygon] = {}
    for feature in source["features"]:
        props = feature["properties"]
        key = (props["icao"], parse_timestamp(props["timestamp"]))
        poly = Polygon(feature["geometry"]["coordinates"][0])
        if not poly.is_valid:
            raise ValueError(f"Ring {key[0]} @ {props['timestamp']} is not a valid polygon")
        if key in polygons:
            raise ValueError(f"Duplicate ring for {key[0]} @ {props['timestamp']}")
        polygons[key] = poly
    return polygons


def check_route(
    route: Route,
    rings: dict[RingKey, Polygon],
    wind_field: WindField,
    airports: list[Airport],
) -> dict:
    """Per-waypoint coverage using only the rings of the snapshot nearest each eta.

    A waypoint exactly on a ring boundary counts as covered (reachable at the limit).
    ``gap_count`` is the number of uncovered waypoints.
    """
    results = []
    for wp in route.waypoints:
        snapshot_time = wind_field.nearest_snapshot(wp.eta).timestamp
        candidates = {icao: poly for (icao, ts), poly in rings.items() if ts == snapshot_time}
        if not candidates:
            raise ValueError(f"No rings for snapshot {format_timestamp(snapshot_time)}")

        point = Point(wp.lon, wp.lat)
        covering = sorted(icao for icao, poly in candidates.items() if poly.covers(point))

        nearest = min(airports, key=lambda a: haversine(wp.lat, wp.lon, a.lat, a.lon))
        results.append({
            "lat": wp.lat,
            "lon": wp.lon,
            "eta": format_timestamp(wp.eta),
            "snapshot_used": format_timestamp(snapshot_time),
            "covered": bool(covering),
            "covering_airports": covering,
            "nearest_airport": nearest.icao,
            "nearest_airport_nm": round(haversine(wp.lat, wp.lon, nearest.lat, nearest.lon), 2),
        })

    gap_count = sum(not r["covered"] for r in results)
    return {"waypoints": results, "fully_covered": gap_count == 0, "gap_count": gap_count}
