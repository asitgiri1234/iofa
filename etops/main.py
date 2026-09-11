"""Entry point: compute wind-adjusted rings (route coverage not yet implemented)."""

import json
import logging
from pathlib import Path

from etops.loaders import load_aircraft, load_airports
from etops.rings import build_all_rings
from etops.wind import WindField

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    airports = load_airports()
    aircraft = load_aircraft()
    wind_field = WindField.from_file()

    rings = build_all_rings(airports, aircraft, wind_field)

    OUTPUT_DIR.mkdir(exist_ok=True)
    rings_path = OUTPUT_DIR / "rings.geojson"
    rings_path.write_text(json.dumps(rings, indent=2), encoding="utf-8")
    print(f"Wrote {len(rings['features'])} ring polygons to {rings_path}")


if __name__ == "__main__":
    main()
