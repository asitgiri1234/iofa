"""Entry point: compute wind-adjusted rings and the time-aware route coverage report."""

import json
import logging
from pathlib import Path

from etops.coverage import check_route, load_ring_polygons
from etops.loaders import load_aircraft, load_airports, load_route
from etops.rings import build_all_rings
from etops.wind import WindField

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    airports = load_airports()
    aircraft = load_aircraft()
    route = load_route()
    wind_field = WindField.from_file()

    OUTPUT_DIR.mkdir(exist_ok=True)

    rings = build_all_rings(airports, aircraft, wind_field)
    rings_path = OUTPUT_DIR / "rings.geojson"
    rings_path.write_text(json.dumps(rings, indent=2), encoding="utf-8")
    print(f"Wrote {len(rings['features'])} ring polygons to {rings_path}")

    report = check_route(route, load_ring_polygons(rings_path), wind_field, airports)
    coverage_path = OUTPUT_DIR / "coverage.json"
    coverage_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote coverage report to {coverage_path}")

    for wp in report["waypoints"]:
        status = "covered" if wp["covered"] else "GAP    "
        airports_str = ", ".join(wp["covering_airports"]) or "-"
        print(
            f"  {wp['eta']}  ({wp['lat']:8.4f}, {wp['lon']:9.4f})  snap {wp['snapshot_used'][11:16]}Z  "
            f"{status}  by {airports_str:<22} nearest {wp['nearest_airport']} {wp['nearest_airport_nm']:7.1f} nm"
        )
    print(f"fully_covered={report['fully_covered']}  gap_count={report['gap_count']}")


if __name__ == "__main__":
    main()
