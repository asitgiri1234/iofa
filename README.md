# Wind-adjusted diversion range rings (ETOPS assessment)

Computes a wind-adjusted 180-minute diversion ring ("egg shape") for each candidate
airport at each of five 6-hourly wind snapshots, then checks whether every waypoint of a
route falls inside at least one ring **from the snapshot nearest that waypoint's ETA**.

## How to run

Python 3.10+ (developed on 3.13). From the repository root:

```bash
pip install -r etops/requirements.txt

python etops/main.py              # writes the three output files (below)
pytest etops                      # full test suite
streamlit run etops/app.py        # interactive app
```

`main.py` writes to `etops/outputs/`:

| File | Contents |
|---|---|
| `rings.geojson` | FeatureCollection of 25 Polygons (5 airports × 5 snapshots), properties `icao`, `aircraft`, `timestamp` (+ `wind_u_kt`, `wind_v_kt`) |
| `coverage.json` | Per-waypoint result plus `fully_covered` and `gap_count` |
| `coverage_map.html` | Standalone Folium map — open it in a browser |

The Streamlit app runs on the same core (`etops/pipeline.py`). It uses the bundled sample
JSON or any files you upload (missing uploads fall back to the sample), has a slider that
steps through the five snapshots so you can watch the rings change shape, embeds the map,
shows the per-waypoint coverage table, and offers downloads of `rings.geojson`,
`coverage.json` and the map.

**Streamlit Community Cloud:** point the app at `etops/app.py`. Dependencies come from
`etops/requirements.txt` (next to the entry point) and the theme from `.streamlit/config.toml`
at the repository root.

## Result for the sample route (MSY → CDG)

| WP | ETA (Z) | Position | Snapshot | Covered by |
|---|---|---|---|---|
| 1 | 00:00 | 29.99, -90.26 | 00Z | **— gap** (nearest airport CYQX, 1979.5 nm) |
| 2 | 02:13 | 35.00, -70.00 | 00Z | CYQX, CYYT |
| 3 | 03:50 | 40.00, -55.00 | 06Z | CYQX, CYYT |
| 4 | 04:56 | 45.00, -45.00 | 06Z | CYQX, CYYT, LPLA |
| 5 | 05:53 | 48.00, -35.00 | 06Z | all five |
| 6 | 06:44 | 50.00, -25.00 | 06Z | all five |
| 7 | 07:33 | 49.50, -15.00 | 06Z | BIKF, EINN, LPLA |
| 8 | 08:22 | 49.00, -5.00 | 06Z | BIKF, EINN, LPLA |
| 9 | 08:59 | 49.01, 2.55 | 06Z | BIKF, EINN |

`fully_covered: false`, `gap_count: 1`. **This is the correct answer, not a bug**: the
route begins near New Orleans, about 1,980 nm from the closest of the five diversion
airports, well beyond any ring (still-air radius 1,290 nm; the largest wind-stretched reach
in any of the 25 rings is 1,480.8 nm, Keflavik at 26 Jul 00Z).

## Assumptions

Requested:

- **Snapshot ties break to the earlier snapshot.** An ETA exactly halfway between two
  snapshots (e.g. 03:00Z between 00Z and 06Z) uses the earlier one.
- **Out-of-grid wind lookups clamp to the nearest edge cell.** The wind grid covers lat
  35–65, lon -60 to -10; a position outside is clamped to that box before the
  nearest-point search, and a warning is logged. Shannon (EINN, lon -8.92) is the only
  airport affected.
- **Wind is sampled once, at the airport**, per snapshot, and the same (u, v) is reused for
  all 72 bearings. Wind along the diversion path is not integrated.
- **Nearest-neighbour in both time and space, no interpolation.** Time is resolved first
  (nearest snapshot), then the nearest grid point *within that snapshot only*, by
  great-circle distance.
- **GeoJSON coordinates are `[lon, lat]`, and every ring is closed** (73 positions, the
  first repeated last).
- **The sample route is genuinely not fully covered**: it starts near New Orleans, far from
  all five diversion airports (see above).

Additional judgement calls:

- **Spherical earth**, R = 3440.065 nm; destination points use the standard great-circle
  formula, bearings clockwise from true north.
- **Wind component** = `u·sin(b) + v·cos(b)` (positive = tailwind), exactly as specified.
  Groundspeed is floored at zero so an (unrealistic) headwind stronger than the diversion
  speed yields zero reach rather than a point flipped behind the airport.
- **Ring winding**: bearings sweep clockwise, so the GeoJSON ring is written reversed to be
  counter-clockwise per RFC 7946. The first (and last) position is still the bearing-0 point.
- **Point-in-polygon** uses shapely in the planar (lon, lat) plane with `covers`, so a
  waypoint exactly on a ring's edge counts as covered. Ring edges between the 5°-spaced
  vertices are therefore straight in lon/lat rather than great-circle arcs, a negligible
  difference except for waypoints right on a ring edge.
- **`gap_count`** is the number of uncovered waypoints (not the number of contiguous
  uncovered stretches). For the sample route the two readings agree.
- **`nearest_airport_nm`** is the great-circle distance to the closest airport's position,
  whether or not that airport's ring covers the waypoint.
- **Map**: by default it draws, for each waypoint, only the five rings of the snapshot used
  for its check (00Z for WP 1–2, 06Z for WP 3–9), one toggleable layer per snapshot. The
  route is drawn as straight segments between waypoints.
- **Timestamps must carry a timezone** (`Z` or an offset); naive timestamps are rejected.
- **Not handled**: rings that cross the antimeridian or enclose a pole. None of the sample
  rings do (the widest, around Keflavik, spans lon -73 to +42 and reaches 85.7°N).

## Verification

The tests reproduce `worked_example.pdf` exactly: at Gander, ETA 05:00Z selects the 06:00Z
snapshot and grid point (49, -54) with u = 32.0, v = -2.4. The ring distances at
0/90/180/270° are 1282.80 / 1386.00 / 1297.20 / 1194.00 nm, and the eastward reach across
the five snapshots is 1376.10 → 1422.00 nm. They also check that the ring is a perfect
1290 nm circle in still air, that it bulges downwind, that each waypoint uses only its own
snapshot's rings, and that the app runs headlessly across all five snapshots.

## Layout

```
etops/
  data/          sample JSON inputs
  etops/         loaders, geo, wind, rings, coverage, mapping, pipeline
  outputs/       rings.geojson, coverage.json, coverage_map.html
  tests/
  main.py        CLI: writes the three outputs
  app.py         Streamlit app
```
