"""Time-varying wind lookup: nearest snapshot in time, then nearest grid point in space.

No interpolation in either dimension.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from etops.geo import haversine
from etops.loaders import DATA_DIR, WindPoint, WindSnapshot, load_wind_grid, parse_timestamp

logger = logging.getLogger(__name__)


def _as_datetime(when: datetime | str) -> datetime:
    if isinstance(when, str):
        return parse_timestamp(when)
    if when.tzinfo is None:
        raise ValueError(f"Datetime has no timezone: {when!r}")
    return when


class WindField:
    """All wind snapshots, queryable by lat/lon/time."""

    def __init__(self, snapshots: list[WindSnapshot]):
        if not snapshots:
            raise ValueError("WindField needs at least one snapshot")
        if any(not s.grid for s in snapshots):
            raise ValueError("Every wind snapshot must have at least one grid point")
        self.snapshots = sorted(snapshots, key=lambda s: s.timestamp)
        # (lat_min, lat_max, lon_min, lon_max) per snapshot, used for edge clamping.
        self._bounds = {
            s.timestamp: (
                min(p.lat for p in s.grid),
                max(p.lat for p in s.grid),
                min(p.lon for p in s.grid),
                max(p.lon for p in s.grid),
            )
            for s in self.snapshots
        }

    @classmethod
    def from_file(cls, path: Path | str = DATA_DIR / "sample_wind_grid.json") -> WindField:
        return cls(load_wind_grid(path))

    def nearest_snapshot(self, when: datetime | str) -> WindSnapshot:
        """Snapshot whose timestamp is closest to ``when``; ties go to the earlier one."""
        when = _as_datetime(when)
        return min(self.snapshots, key=lambda s: (abs(s.timestamp - when), s.timestamp))

    def nearest_grid_point(self, snapshot: WindSnapshot, lat: float, lon: float) -> WindPoint:
        """Nearest grid point (great-circle distance) within ``snapshot`` only.

        Positions outside the grid's lat/lon extent are clamped to the nearest edge
        first, with a warning. Equidistant grid points resolve to the first in file order.
        """
        lat_min, lat_max, lon_min, lon_max = self._bounds[snapshot.timestamp]
        clamped_lat = min(max(lat, lat_min), lat_max)
        clamped_lon = min(max(lon, lon_min), lon_max)
        if (clamped_lat, clamped_lon) != (lat, lon):
            logger.warning(
                "Position (%.4f, %.4f) is outside the wind grid "
                "(lat %.1f..%.1f, lon %.1f..%.1f); clamping to (%.4f, %.4f)",
                lat, lon, lat_min, lat_max, lon_min, lon_max, clamped_lat, clamped_lon,
            )
        return min(snapshot.grid, key=lambda p: haversine(clamped_lat, clamped_lon, p.lat, p.lon))

    def wind_at(self, lat: float, lon: float, when: datetime | str) -> tuple[float, float]:
        """(u, v) in knots: resolve the snapshot in time first, then the grid point in space."""
        snapshot = self.nearest_snapshot(when)
        point = self.nearest_grid_point(snapshot, lat, lon)
        return point.u, point.v
