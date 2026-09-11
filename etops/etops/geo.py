"""Great-circle geometry on a spherical earth, in nautical miles.

Bearings are degrees clockwise from true north (0 = N, 90 = E).
"""

from __future__ import annotations

import math

EARTH_RADIUS_NM = 3440.065


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in nautical miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    # Clamp guards against a drifting fractionally above 1 for antipodal points.
    return 2 * EARTH_RADIUS_NM * math.asin(math.sqrt(min(1.0, a)))


def destination_point(lat: float, lon: float, bearing_deg: float, distance_nm: float) -> tuple[float, float]:
    """Point reached travelling ``distance_nm`` along a great circle from (lat, lon)
    on initial bearing ``bearing_deg``. Returns (lat, lon) with lon in [-180, 180).
    """
    phi1 = math.radians(lat)
    lmb1 = math.radians(lon)
    theta = math.radians(bearing_deg)
    delta = distance_nm / EARTH_RADIUS_NM  # angular distance

    sin_phi2 = math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta)
    phi2 = math.asin(max(-1.0, min(1.0, sin_phi2)))
    lmb2 = lmb1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * sin_phi2,
    )

    lon2 = (math.degrees(lmb2) + 540.0) % 360.0 - 180.0
    return math.degrees(phi2), lon2
