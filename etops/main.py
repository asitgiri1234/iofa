"""Entry point: compute wind-adjusted rings and route coverage (not yet implemented)."""

from etops.loaders import load_aircraft, load_airports, load_route, load_wind_grid


def main() -> None:
    airports = load_airports()
    aircraft = load_aircraft()
    route = load_route()
    snapshots = load_wind_grid()
    print(
        f"Loaded {len(airports)} airports, aircraft {aircraft.aircraft} "
        f"(still-air radius {aircraft.still_air_radius_nm:.1f} nm), "
        f"{len(route.waypoints)} waypoints, {len(snapshots)} wind snapshots."
    )


if __name__ == "__main__":
    main()
