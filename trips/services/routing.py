"""Geocoding and routing providers.

Uses Nominatim (OSM) for geocoding and OpenRouteService for directions.
Falls back to a deterministic mock router when no API key is configured
(useful for local development and unit tests).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings


class RoutingError(Exception):
    """Raised when geocoding or routing fails with a user-facing message."""


@dataclass(frozen=True)
class GeoPoint:
    label: str
    lat: float
    lon: float


def _haversine_miles(a: GeoPoint, b: GeoPoint) -> float:
    r = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [a.lat, a.lon, b.lat, b.lon])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(h))


def geocode(query: str) -> GeoPoint:
    """Geocode an address via Nominatim, with a small built-in city fallback."""
    known = _KNOWN_PLACES.get(query.strip().lower())
    if known:
        return GeoPoint(label=query, lat=known[0], lon=known[1])

    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": settings.GEOCODER_USER_AGENT}
    params = {"q": query, "format": "json", "limit": 1}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise RoutingError(f"Geocoding failed for '{query}'.") from exc

    if not data:
        raise RoutingError(f"Could not find location: '{query}'.")

    item = data[0]
    return GeoPoint(
        label=item.get("display_name", query),
        lat=float(item["lat"]),
        lon=float(item["lon"]),
    )


def build_route(
    current: GeoPoint,
    pickup: GeoPoint,
    dropoff: GeoPoint,
) -> dict[str, Any]:
    """Return route geometry and metrics for current → pickup → dropoff."""
    api_key = settings.OPENROUTESERVICE_API_KEY
    if not api_key:
        return _mock_route(current, pickup, dropoff)
    return _ors_route(api_key, current, pickup, dropoff)


def _ors_route(
    api_key: str,
    current: GeoPoint,
    pickup: GeoPoint,
    dropoff: GeoPoint,
) -> dict[str, Any]:
    url = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    body = {
        "coordinates": [
            [current.lon, current.lat],
            [pickup.lon, pickup.lat],
            [dropoff.lon, dropoff.lat],
        ],
        "instructions": True,
        "units": "mi",
    }
    try:
        response = requests.post(url, json=body, headers=headers, timeout=30)
        if response.status_code == 429:
            raise RoutingError("Routing provider rate limit reached. Try again shortly.")
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise RoutingError("Directions request failed. Check the routing API key.") from exc

    features = payload.get("features") or []
    if not features:
        raise RoutingError("No route found between the given locations.")

    feature = features[0]
    props = feature.get("properties") or {}
    summary = props.get("summary") or {}
    segments = props.get("segments") or []

    maneuvers: list[dict[str, Any]] = []
    for seg in segments:
        for step in seg.get("steps") or []:
            maneuvers.append(
                {
                    "instruction": step.get("instruction", ""),
                    "distanceMiles": round(float(step.get("distance", 0)), 2),
                    "durationMinutes": round(float(step.get("duration", 0)) / 60.0, 2),
                    "type": step.get("type"),
                }
            )

    geometry = feature.get("geometry") or {}
    distance_miles = float(summary.get("distance", 0))
    duration_hours = float(summary.get("duration", 0)) / 3600.0

    # Split legs approximately by waypoint order for HOS fuel/drive planning.
    leg_current_to_pickup = _haversine_miles(current, pickup) * 1.2
    leg_pickup_to_dropoff = max(distance_miles - leg_current_to_pickup, 0.1)
    if distance_miles > 0:
        scale = distance_miles / (leg_current_to_pickup + leg_pickup_to_dropoff)
        leg_current_to_pickup *= scale
        leg_pickup_to_dropoff *= scale

    avg_speed = distance_miles / duration_hours if duration_hours > 0 else 55.0

    return {
        "geometry": geometry,
        "totalDistanceMiles": round(distance_miles, 2),
        "totalDurationHours": round(duration_hours, 3),
        "averageSpeedMph": round(avg_speed, 2),
        "legs": [
            {
                "from": "current",
                "to": "pickup",
                "distanceMiles": round(leg_current_to_pickup, 2),
                "durationHours": round(leg_current_to_pickup / avg_speed, 3),
            },
            {
                "from": "pickup",
                "to": "dropoff",
                "distanceMiles": round(leg_pickup_to_dropoff, 2),
                "durationHours": round(leg_pickup_to_dropoff / avg_speed, 3),
            },
        ],
        "waypoints": [
            {"role": "current", "label": current.label, "lat": current.lat, "lon": current.lon},
            {"role": "pickup", "label": pickup.label, "lat": pickup.lat, "lon": pickup.lon},
            {"role": "dropoff", "label": dropoff.label, "lat": dropoff.lat, "lon": dropoff.lon},
        ],
        "maneuvers": maneuvers,
        "provider": "openrouteservice",
    }


def _mock_route(current: GeoPoint, pickup: GeoPoint, dropoff: GeoPoint) -> dict[str, Any]:
    """Deterministic offline route for demos/tests without an API key."""
    d1 = _haversine_miles(current, pickup) * 1.25
    d2 = _haversine_miles(pickup, dropoff) * 1.25
    # Ensure demo multi-day feasibility for distant city pairs.
    d1 = max(d1, 1.0)
    d2 = max(d2, 1.0)
    total = d1 + d2
    avg_speed = 55.0
    duration = total / avg_speed

    geometry = {
        "type": "LineString",
        "coordinates": [
            [current.lon, current.lat],
            [pickup.lon, pickup.lat],
            [dropoff.lon, dropoff.lat],
        ],
    }

    return {
        "geometry": geometry,
        "totalDistanceMiles": round(total, 2),
        "totalDurationHours": round(duration, 3),
        "averageSpeedMph": avg_speed,
        "legs": [
            {
                "from": "current",
                "to": "pickup",
                "distanceMiles": round(d1, 2),
                "durationHours": round(d1 / avg_speed, 3),
            },
            {
                "from": "pickup",
                "to": "dropoff",
                "distanceMiles": round(d2, 2),
                "durationHours": round(d2 / avg_speed, 3),
            },
        ],
        "waypoints": [
            {"role": "current", "label": current.label, "lat": current.lat, "lon": current.lon},
            {"role": "pickup", "label": pickup.label, "lat": pickup.lat, "lon": pickup.lon},
            {"role": "dropoff", "label": dropoff.label, "lat": dropoff.lat, "lon": dropoff.lon},
        ],
        "maneuvers": [
            {
                "instruction": f"Drive from current location to pickup ({round(d1, 1)} mi)",
                "distanceMiles": round(d1, 2),
                "durationMinutes": round((d1 / avg_speed) * 60, 2),
                "type": "drive",
            },
            {
                "instruction": f"Drive from pickup to dropoff ({round(d2, 1)} mi)",
                "distanceMiles": round(d2, 2),
                "durationMinutes": round((d2 / avg_speed) * 60, 2),
                "type": "drive",
            },
        ],
        "provider": "mock",
    }


# Small built-in gazetteer so demos work offline / without Nominatim rate limits.
_KNOWN_PLACES: dict[str, tuple[float, float]] = {
    "chicago, il": (41.8781, -87.6298),
    "chicago": (41.8781, -87.6298),
    "dallas, tx": (32.7767, -96.7970),
    "dallas": (32.7767, -96.7970),
    "atlanta, ga": (33.7490, -84.3880),
    "atlanta": (33.7490, -84.3880),
    "denver, co": (39.7392, -104.9903),
    "denver": (39.7392, -104.9903),
    "los angeles, ca": (34.0522, -118.2437),
    "los angeles": (34.0522, -118.2437),
    "new york, ny": (40.7128, -74.0060),
    "new york": (40.7128, -74.0060),
    "kansas city, mo": (39.0997, -94.5786),
    "kansas city": (39.0997, -94.5786),
    "memphis, tn": (35.1495, -90.0490),
    "memphis": (35.1495, -90.0490),
    "phoenix, az": (33.4484, -112.0740),
    "phoenix": (33.4484, -112.0740),
    "seattle, wa": (47.6062, -122.3321),
    "seattle": (47.6062, -122.3321),
    "richmond, va": (37.5407, -77.4360),
    "richmond": (37.5407, -77.4360),
    "newark, nj": (40.7357, -74.1724),
    "newark": (40.7357, -74.1724),
}


def geocode_with_backoff(query: str) -> GeoPoint:
    """Geocode with a brief pause to respect Nominatim usage policy."""
    point = geocode(query)
    # Only sleep when we actually hit the network.
    if query.strip().lower() not in _KNOWN_PLACES:
        time.sleep(1.0)
    return point
