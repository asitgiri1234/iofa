"""Load the sample JSON inputs into typed dataclasses.

All timestamps are parsed into timezone-aware ``datetime`` objects (UTC).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Airport:
    icao: str
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class Aircraft:
    aircraft: str
    diversion_speed_kt: float
    cruise_speed_kt: float
    rating_minutes: float

    @property
    def still_air_radius_nm(self) -> float:
        return self.diversion_speed_kt * (self.rating_minutes / 60)


@dataclass(frozen=True)
class Waypoint:
    lat: float
    lon: float
    eta: datetime


@dataclass(frozen=True)
class Route:
    origin: str
    destination: str
    departure_time: datetime
    cruise_speed_kt: float
    waypoints: list[Waypoint]


@dataclass(frozen=True)
class WindPoint:
    lat: float
    lon: float
    u: float  # eastward component, knots
    v: float  # northward component, knots


@dataclass(frozen=True)
class WindSnapshot:
    timestamp: datetime
    grid: list[WindPoint]


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp such as ``2026-07-25T00:00:00Z``.

    Naive timestamps are rejected rather than silently assumed to be UTC.
    """
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"Timestamp has no timezone: {value!r}")
    return dt


def format_timestamp(dt: datetime) -> str:
    """Inverse of ``parse_timestamp``: ``2026-07-25T06:00:00Z``."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path | str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# parse_* build dataclasses from already-decoded JSON (e.g. a Streamlit upload);
# load_* read the file and delegate.

def parse_airports(data: list[dict]) -> list[Airport]:
    return [
        Airport(icao=a["icao"], name=a["name"], lat=float(a["lat"]), lon=float(a["lon"]))
        for a in data
    ]


def parse_aircraft(a: dict) -> Aircraft:
    return Aircraft(
        aircraft=a["aircraft"],
        diversion_speed_kt=float(a["diversion_speed_kt"]),
        cruise_speed_kt=float(a["cruise_speed_kt"]),
        rating_minutes=float(a["rating_minutes"]),
    )


def parse_route(r: dict) -> Route:
    return Route(
        origin=r["origin"],
        destination=r["destination"],
        departure_time=parse_timestamp(r["departure_time"]),
        cruise_speed_kt=float(r["cruise_speed_kt"]),
        waypoints=[
            Waypoint(lat=float(w["lat"]), lon=float(w["lon"]), eta=parse_timestamp(w["eta"]))
            for w in r["waypoints"]
        ],
    )


def parse_wind_grid(data: list[dict]) -> list[WindSnapshot]:
    """All wind snapshots, sorted by timestamp."""
    snapshots = [
        WindSnapshot(
            timestamp=parse_timestamp(s["timestamp"]),
            grid=[
                WindPoint(lat=float(p["lat"]), lon=float(p["lon"]), u=float(p["u"]), v=float(p["v"]))
                for p in s["grid"]
            ],
        )
        for s in data
    ]
    return sorted(snapshots, key=lambda s: s.timestamp)


def load_airports(path: Path | str = DATA_DIR / "sample_airports.json") -> list[Airport]:
    return parse_airports(_read_json(path))


def load_aircraft(path: Path | str = DATA_DIR / "sample_aircraft.json") -> Aircraft:
    return parse_aircraft(_read_json(path))


def load_route(path: Path | str = DATA_DIR / "sample_route.json") -> Route:
    return parse_route(_read_json(path))


def load_wind_grid(path: Path | str = DATA_DIR / "sample_wind_grid.json") -> list[WindSnapshot]:
    return parse_wind_grid(_read_json(path))
