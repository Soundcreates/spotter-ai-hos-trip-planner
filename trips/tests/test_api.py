"""API tests for trip planning endpoints."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from trips.services.routing import GeoPoint


@pytest.fixture
def api():
    return APIClient()


def _fake_geocode(query: str) -> GeoPoint:
    mapping = {
        "Chicago, IL": GeoPoint("Chicago, IL", 41.8781, -87.6298),
        "Dallas, TX": GeoPoint("Dallas, TX", 32.7767, -96.7970),
        "Atlanta, GA": GeoPoint("Atlanta, GA", 33.7490, -84.3880),
    }
    return mapping.get(query, GeoPoint(query, 40.0, -90.0))


@pytest.mark.django_db
def test_health(api):
    res = api.get("/api/health/")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.django_db
def test_plan_validation_rejects_bad_cycle(api):
    res = api.post(
        "/api/trips/plan/",
        {
            "currentLocation": "Chicago, IL",
            "pickupLocation": "Dallas, TX",
            "dropoffLocation": "Atlanta, GA",
            "currentCycleUsedHours": 80,
        },
        format="json",
    )
    assert res.status_code == 400


@pytest.mark.django_db
@patch("trips.views.geocode", side_effect=_fake_geocode)
def test_plan_creates_trip(mock_geo, api):
    res = api.post(
        "/api/trips/plan/",
        {
            "currentLocation": "Chicago, IL",
            "pickupLocation": "Dallas, TX",
            "dropoffLocation": "Atlanta, GA",
            "currentCycleUsedHours": 12,
            "shiftStart": datetime(2026, 3, 1, 6, 0, tzinfo=timezone.utc).isoformat(),
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    body = res.json()
    assert "tripId" in body
    assert "route" in body
    assert "itinerary" in body
    assert "logs" in body
    assert body["logs"][0]["totals"]["all"] == 24.0

    detail = api.get(f"/api/trips/{body['tripId']}/")
    assert detail.status_code == 200
    assert detail.json()["tripId"] == body["tripId"]


@pytest.mark.django_db
def test_missing_fields(api):
    res = api.post("/api/trips/plan/", {}, format="json")
    assert res.status_code == 400
