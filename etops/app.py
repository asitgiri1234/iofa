"""Streamlit front end for the ETOPS wind-adjusted ring / route-coverage core.

Run from the repository root:  streamlit run etops/app.py
"""

from __future__ import annotations

import json
import math

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from etops.loaders import (
    DATA_DIR,
    parse_aircraft,
    parse_airports,
    parse_route,
    parse_wind_grid,
)
from etops.mapping import build_coverage_map
from etops.pipeline import run_pipeline
from etops.wind import WindField

INPUTS = {
    "airports": ("Airports", "sample_airports.json"),
    "aircraft": ("Aircraft performance", "sample_aircraft.json"),
    "wind": ("Wind grid (time snapshots)", "sample_wind_grid.json"),
    "route": ("Route", "sample_route.json"),
}
PER_WAYPOINT = "Per waypoint (as checked)"

st.set_page_config(page_title="ETOPS Diversion Rings", page_icon="✈️", layout="wide")


def read_inputs() -> tuple[dict[str, str], list[str]]:
    """Raw JSON text per input, plus the labels of inputs that fell back to the sample."""
    st.sidebar.header("Inputs")
    source = st.sidebar.radio("Data source", ["Bundled sample", "Upload JSON"], horizontal=True)
    texts, defaulted = {}, []
    for key, (label, filename) in INPUTS.items():
        uploaded = None
        if source == "Upload JSON":
            uploaded = st.sidebar.file_uploader(label, type="json", key=f"upload_{key}")
        if uploaded is not None:
            texts[key] = uploaded.getvalue().decode("utf-8")
        else:
            texts[key] = (DATA_DIR / filename).read_text(encoding="utf-8")
            defaulted.append(label)
    if source == "Upload JSON" and defaulted:
        st.sidebar.caption("Using the bundled sample for: " + ", ".join(defaulted))
    return texts, defaulted


@st.cache_data(show_spinner="Computing rings and coverage…")
def compute(airports_json: str, aircraft_json: str, wind_json: str, route_json: str):
    airports = parse_airports(json.loads(airports_json))
    aircraft = parse_aircraft(json.loads(aircraft_json))
    route = parse_route(json.loads(route_json))
    wind_field = WindField(parse_wind_grid(json.loads(wind_json)))
    rings, report = run_pipeline(airports, aircraft, route, wind_field)
    return airports, aircraft, rings, report


def coverage_table(report: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "WP": n,
                "ETA": wp["eta"],
                "Snapshot used": wp["snapshot_used"],
                "Lat": wp["lat"],
                "Lon": wp["lon"],
                "Covered": wp["covered"],
                "Covering airports": ", ".join(wp["covering_airports"]) or "—",
                "Nearest airport": wp["nearest_airport"],
                "Nearest (nm)": wp["nearest_airport_nm"],
            }
            for n, wp in enumerate(report["waypoints"], 1)
        ]
    )


def ring_wind_table(rings: dict, snapshot: str) -> pd.DataFrame:
    rows = []
    for f in rings["features"]:
        p = f["properties"]
        if p["timestamp"] == snapshot:
            u, v = p["wind_u_kt"], p["wind_v_kt"]
            rows.append({
                "Airport": p["icao"],
                "u (kt, east)": u,
                "v (kt, north)": v,
                "Wind speed (kt)": round((u * u + v * v) ** 0.5, 1),
                "Bulges toward (°)": round(math.degrees(math.atan2(u, v)) % 360),
            })
    return pd.DataFrame(rows)


def main() -> None:
    st.title("✈️ Wind-adjusted diversion rings")
    st.caption(
        "Each airport's reachable area within the rating time, stretched by the wind at that "
        "airport for each 6-hourly snapshot. Each waypoint is checked only against the rings of "
        "the snapshot nearest its ETA."
    )

    texts, _ = read_inputs()
    try:
        airports, aircraft, rings, report = compute(texts["airports"], texts["aircraft"], texts["wind"], texts["route"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        st.error(f"Could not process the inputs: {exc}")
        st.stop()

    snapshots = sorted({f["properties"]["timestamp"] for f in rings["features"]})
    covered = sum(wp["covered"] for wp in report["waypoints"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Route", "Fully covered" if report["fully_covered"] else "Not fully covered")
    c2.metric("Gaps", report["gap_count"])
    c3.metric("Waypoints covered", f"{covered} / {len(report['waypoints'])}")
    c4.metric(f"{aircraft.aircraft} still-air radius", f"{aircraft.still_air_radius_nm:,.0f} nm")

    view = st.select_slider(
        "Rings to show — step through the wind snapshots to watch the rings change shape",
        options=[PER_WAYPOINT, *snapshots],
        format_func=lambda s: s if s == PER_WAYPOINT else f"{s[:10]} {s[11:16]}Z",
    )
    if view == PER_WAYPOINT:
        fmap = build_coverage_map(rings, report, airports)
        st.caption("Showing, for each waypoint, only the rings from the snapshot used for its check.")
    else:
        fmap = build_coverage_map(rings, report, airports, snapshots=[view])
        st.caption(
            f"Showing all rings at {view}. Waypoint colours still reflect each waypoint's own "
            "snapshot, so they may not match these rings."
        )

    map_html = fmap.get_root().render()
    components.html(map_html, height=640)

    if view != PER_WAYPOINT:
        st.subheader(f"Wind at each airport — {view}")
        st.dataframe(ring_wind_table(rings, view), hide_index=True, width="stretch")

    st.subheader("Per-waypoint coverage")
    st.dataframe(
        coverage_table(report),
        hide_index=True,
        width="stretch",
        column_config={
            "Covered": st.column_config.CheckboxColumn(),
            "Lat": st.column_config.NumberColumn(format="%.4f"),
            "Lon": st.column_config.NumberColumn(format="%.4f"),
            "Nearest (nm)": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    st.subheader("Downloads")
    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "rings.geojson", json.dumps(rings, indent=2), file_name="rings.geojson",
        mime="application/geo+json", width="stretch",
    )
    d2.download_button(
        "coverage.json", json.dumps(report, indent=2), file_name="coverage.json",
        mime="application/json", width="stretch",
    )
    d3.download_button(
        "coverage_map.html", build_coverage_map(rings, report, airports).get_root().render(),
        file_name="coverage_map.html", mime="text/html", width="stretch",
    )


main()
