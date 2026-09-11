"""The shared core used by both main.py and the Streamlit app."""

from __future__ import annotations

from etops.coverage import check_route, load_ring_polygons
from etops.loaders import Aircraft, Airport, Route
from etops.rings import build_all_rings
from etops.wind import WindField


def run_pipeline(
    airports: list[Airport],
    aircraft: Aircraft,
    route: Route,
    wind_field: WindField,
) -> tuple[dict, dict]:
    """Return (rings FeatureCollection, coverage report)."""
    rings = build_all_rings(airports, aircraft, wind_field)
    report = check_route(route, load_ring_polygons(rings), wind_field, airports)
    return rings, report
