"""Entry point: write rings.geojson, coverage.json and coverage_map.html to outputs/."""

import json
import logging
from pathlib import Path

from etops.loaders import load_aircraft, load_airports, load_route
from etops.mapping import build_coverage_map
from etops.pipeline import run_pipeline
from etops.wind import WindField

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    airports = load_airports()
    aircraft = load_aircraft()
    route = load_route()
    wind_field = WindField.from_file()

    rings, report = run_pipeline(airports, aircraft, route, wind_field)

    OUTPUT_DIR.mkdir(exist_ok=True)
    rings_path = OUTPUT_DIR / "rings.geojson"
    coverage_path = OUTPUT_DIR / "coverage.json"
    map_path = OUTPUT_DIR / "coverage_map.html"

    rings_path.write_text(json.dumps(rings, indent=2), encoding="utf-8")
    coverage_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    build_coverage_map(rings, report, airports).save(str(map_path))

    print(f"Wrote {len(rings['features'])} ring polygons to {rings_path}")
    print(f"Wrote coverage report to {coverage_path}")
    print(f"Wrote map to {map_path}")

    for wp in report["waypoints"]:
        status = "covered" if wp["covered"] else "GAP    "
        airports_str = ", ".join(wp["covering_airports"]) or "-"
        print(
            f"  {wp['eta']}  ({wp['lat']:8.4f}, {wp['lon']:9.4f})  snap {wp['snapshot_used'][11:16]}Z  "
            f"{status}  by {airports_str:<28} nearest {wp['nearest_airport']} {wp['nearest_airport_nm']:7.1f} nm"
        )
    print(f"fully_covered={report['fully_covered']}  gap_count={report['gap_count']}")


if __name__ == "__main__":
    main()
