"""Folium map of the wind-adjusted rings, the route, and per-waypoint coverage."""

from __future__ import annotations

from html import escape

import folium

from etops.geo import destination_point, haversine
from etops.loaders import Airport

SNAPSHOT_COLORS = ["#1f77b4", "#ff7f0e", "#9467bd", "#8c564b", "#17becf"]  # no red/green
COVERED_COLOR = "#2ca02c"
GAP_COLOR = "#d62728"
ROUTE_COLOR = "#444444"
STILL_AIR_COLOR = "#6b6b6b"
BEARINGS_DEG = tuple(range(0, 360, 5))  # same 72 directions the rings use


def _short(ts: str) -> str:
    """'2026-07-25T06:00:00Z' -> '2026-07-25 06:00Z'."""
    return f"{ts[:10]} {ts[11:16]}Z"


def _ranges(numbers: list[int]) -> str:
    """[1, 2, 3, 5] -> '1-3, 5'. Plain hyphen: folium JSON-escapes non-ASCII in layer names."""
    runs: list[list[int]] = []
    for n in numbers:
        if runs and n == runs[-1][-1] + 1:
            runs[-1].append(n)
        else:
            runs.append([n])
    return ", ".join(str(r[0]) if len(r) == 1 else f"{r[0]}-{r[-1]}" for r in runs)


def _still_air_circle(airport: Airport, radius_nm: float) -> list[tuple[float, float]]:
    """The plain no-wind circle, built with the same bearing sweep as a wind ring
    so the two are directly comparable on the map.
    """
    points = [destination_point(airport.lat, airport.lon, b, radius_nm) for b in BEARINGS_DEG]
    points.append(points[0])
    return points


def _reach_span(rings_fc: dict, airports: list[Airport]) -> tuple[float, float] | None:
    """(closest, farthest) distance reached by any ring vertex, over every ring."""
    pos = {a.icao: (a.lat, a.lon) for a in airports}
    distances = [
        haversine(*pos[f["properties"]["icao"]], lat, lon)
        for f in rings_fc["features"]
        if f["properties"]["icao"] in pos
        for lon, lat in f["geometry"]["coordinates"][0]
    ]
    return (min(distances), max(distances)) if distances else None


def _popup_html(number: int, wp: dict) -> str:
    status = (
        f'<b style="color:{COVERED_COLOR}">Covered</b>' if wp["covered"]
        else f'<b style="color:{GAP_COLOR}">Not covered (gap)</b>'
    )
    covering = ", ".join(wp["covering_airports"]) or "none"
    return (
        f"<b>Waypoint {number}</b> &mdash; {status}<br>"
        f"{wp['lat']:.4f}, {wp['lon']:.4f}<br>"
        f"ETA: {escape(wp['eta'])}<br>"
        f"Snapshot used: {escape(wp['snapshot_used'])}<br>"
        f"Covered by: {escape(covering)}<br>"
        f"Nearest airport: {escape(wp.get('nearest_airport', '?'))} "
        f"({wp['nearest_airport_nm']:.1f} nm)"
    )


def _legend_html(
    shown: list[str],
    colors: dict[str, str],
    report: dict,
    reach: tuple[float, float] | None = None,
    still_air_nm: float | None = None,
) -> str:
    swatch = (
        '<span style="display:inline-block;width:14px;height:10px;margin-right:6px;'
        'border:2px solid {c};background:{c}22;vertical-align:middle"></span>'
    )
    dot = (
        '<span style="display:inline-block;width:11px;height:11px;border-radius:50%;'
        'margin-right:6px;background:{c};border:1.5px solid #fff;box-shadow:0 0 0 1px #999;'
        'vertical-align:middle"></span>'
    )
    waypoints = report["waypoints"]
    covered = sum(1 for w in waypoints if w["covered"])

    # Summary first: the two numbers a reader wants before any key.
    summary = [
        f'<div style="margin-bottom:2px">{covered} of {len(waypoints)} waypoints covered '
        f'&middot; {report["gap_count"]} gap(s)</div>'
    ]
    if reach:
        near, far = reach
        line = f"Ring reach {near:,.0f}&ndash;{far:,.0f} nm"
        if still_air_nm:
            line += f" &middot; still air {still_air_nm:,.0f} nm"
        summary.append(f'<div style="margin-bottom:4px;color:#555">{line}</div>')

    rows = [
        f"<div>{dot.format(c=COVERED_COLOR)}Covered waypoint</div>",
        f"<div>{dot.format(c=GAP_COLOR)}Uncovered waypoint (gap)</div>",
        '<div><span style="display:inline-block;width:18px;margin-right:6px;'
        f'border-top:2.5px dashed {ROUTE_COLOR};vertical-align:middle"></span>Route</div>',
        '<div><i class="fa fa-plane" style="width:14px;margin-right:6px;color:#0b3d91"></i>'
        "Diversion airport</div>",
    ]
    if still_air_nm:
        rows.append(
            '<div><span style="display:inline-block;width:18px;margin-right:6px;'
            f'border-top:2px dashed {STILL_AIR_COLOR};vertical-align:middle"></span>'
            "Still-air circle (no wind)</div>"
        )
    rows += [
        '<div style="margin-top:6px;font-weight:600">Rings by wind snapshot</div>',
        *(f"<div>{swatch.format(c=colors[ts])}{_short(ts)}</div>" for ts in shown),
    ]
    verdict = (
        '<span style="color:{c};font-weight:600">{t}</span>'.format(
            c=COVERED_COLOR if report["fully_covered"] else GAP_COLOR,
            t="Fully covered" if report["fully_covered"] else f"Not fully covered &mdash; {report['gap_count']} gap(s)",
        )
    )
    return (
        '<div style="position:fixed;bottom:28px;left:12px;z-index:9999;background:#fff;'
        "padding:10px 12px;border-radius:6px;box-shadow:0 1px 5px rgba(0,0,0,.35);"
        'font:12px/1.6 system-ui,-apple-system,Segoe UI,sans-serif;color:#222;max-width:260px">'
        f'<div style="font-weight:700;margin-bottom:4px">180-min wind-adjusted coverage</div>'
        f"{''.join(summary)}"
        f"{''.join(rows)}"
        f'<div style="margin-top:6px">{verdict}</div></div>'
    )


def build_coverage_map(
    rings_fc: dict,
    report: dict,
    airports: list[Airport],
    snapshots: list[str] | None = None,
    still_air_nm: float | None = None,
) -> folium.Map:
    """Folium map of the route, waypoints (coloured by coverage), airports, and rings.

    By default only the rings of snapshots actually used by some waypoint are drawn,
    one toggleable layer per snapshot. Pass ``snapshots`` (timestamp strings) to draw
    other snapshots instead, e.g. to step through all five. Pass ``still_air_nm`` to
    overlay the plain no-wind circle of that radius on each airport, which makes the
    wind distortion of every ring directly visible.
    """
    all_ts = sorted({f["properties"]["timestamp"] for f in rings_fc["features"]})
    colors = {ts: SNAPSHOT_COLORS[i % len(SNAPSHOT_COLORS)] for i, ts in enumerate(all_ts)}

    waypoints = report["waypoints"]
    users: dict[str, list[int]] = {}
    for n, wp in enumerate(waypoints, 1):
        users.setdefault(wp["snapshot_used"], []).append(n)

    shown = sorted(users) if snapshots is None else list(snapshots)
    unknown = set(shown) - set(all_ts)
    if unknown:
        raise ValueError(f"No rings for snapshot(s): {sorted(unknown)}")

    # OpenStreetMap needs no API key (folium 0.20 warns that CartoDB tiles now do).
    m = folium.Map(tiles="OpenStreetMap", control_scale=True)
    # Waypoints get their own pane above the rings so re-toggling a ring layer
    # can't bury them and swallow their clicks.
    folium.map.CustomPane("waypoints", z_index=640, pointer_events=True).add_to(m)
    bounds = [(wp["lat"], wp["lon"]) for wp in waypoints] + [(a.lat, a.lon) for a in airports]

    if still_air_nm:
        still_group = folium.FeatureGroup(name=f"Still-air circle ({still_air_nm:,.0f} nm, no wind)")
        for a in airports:
            folium.PolyLine(
                _still_air_circle(a, still_air_nm),
                color=STILL_AIR_COLOR, weight=1.5, dash_array="5 5", opacity=0.9,
                tooltip=f"{a.icao} still-air circle &mdash; {still_air_nm:,.0f} nm, no wind",
            ).add_to(still_group)
        still_group.add_to(m)

    for ts in shown:
        label = f"Rings @ {_short(ts)}"
        label += f" (WP {_ranges(users[ts])})" if ts in users else " (no waypoints)"
        group = folium.FeatureGroup(name=label, show=True)
        color = colors[ts]
        for feature in rings_fc["features"]:
            props = feature["properties"]
            if props["timestamp"] != ts:
                continue
            folium.GeoJson(
                feature,
                style_function=lambda _f, c=color: {"color": c, "weight": 2, "fillColor": c, "fillOpacity": 0.07},
                highlight_function=lambda _f, c=color: {"weight": 4, "fillOpacity": 0.18},
                tooltip=(
                    f"{props['icao']} ring @ {_short(ts)} "
                    f"(wind u={props.get('wind_u_kt', '?')}, v={props.get('wind_v_kt', '?')} kt)"
                ),
            ).add_to(group)
            bounds += [(lat, lon) for lon, lat in feature["geometry"]["coordinates"][0]]
        group.add_to(m)

    airport_group = folium.FeatureGroup(name="Diversion airports")
    for a in airports:
        folium.Marker(
            [a.lat, a.lon],
            tooltip=f"{a.icao} — {a.name}",
            icon=folium.Icon(color="darkblue", icon="plane", prefix="fa"),
        ).add_to(airport_group)
    airport_group.add_to(m)

    route_group = folium.FeatureGroup(name="Route & waypoints")
    folium.PolyLine(
        [(wp["lat"], wp["lon"]) for wp in waypoints],
        color=ROUTE_COLOR, weight=2.5, dash_array="6 6", tooltip="Route",
    ).add_to(route_group)
    for n, wp in enumerate(waypoints, 1):
        marker = folium.CircleMarker(
            [wp["lat"], wp["lon"]],
            radius=7,
            color="#ffffff",
            weight=1.5,
            fill=True,
            fill_color=COVERED_COLOR if wp["covered"] else GAP_COLOR,
            fill_opacity=1.0,
            tooltip=f"WP {n}: {'covered' if wp['covered'] else 'GAP'} — {_short(wp['eta'])}",
            popup=folium.Popup(_popup_html(n, wp), max_width=300),
        )
        marker.options["pane"] = "waypoints"  # folium's path_options drops a `pane=` kwarg
        marker.add_to(route_group)
    route_group.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    m.get_root().html.add_child(
        folium.Element(_legend_html(shown, colors, report, _reach_span(rings_fc, airports), still_air_nm))
    )

    lats, lons = zip(*bounds)
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
    return m
