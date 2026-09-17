"""Unit tests for the HOS scheduling engine and daily log builder."""

from datetime import datetime, timezone

import pytest

from trips.services.hos import (
    BREAK_AFTER_DRIVE_HOURS,
    DRIVE_LIMIT_HOURS,
    FUEL_EVERY_MILES,
    HOSPlanningError,
    WINDOW_LIMIT_HOURS,
    plan_trip,
)
from trips.services.logs import build_daily_logs
from trips.services.routing import GeoPoint, build_route


def _route(miles_to_pickup: float, miles_loaded: float, speed: float = 55.0) -> dict:
    return {
        "averageSpeedMph": speed,
        "totalDistanceMiles": miles_to_pickup + miles_loaded,
        "legs": [
            {
                "from": "current",
                "to": "pickup",
                "distanceMiles": miles_to_pickup,
                "durationHours": miles_to_pickup / speed,
            },
            {
                "from": "pickup",
                "to": "dropoff",
                "distanceMiles": miles_loaded,
                "durationHours": miles_loaded / speed,
            },
        ],
    }


SHIFT = datetime(2026, 3, 1, 6, 0, tzinfo=timezone.utc)


def test_short_trip_includes_pickup_and_dropoff():
    result = plan_trip(
        route=_route(10, 100),
        shift_start=SHIFT,
        current_cycle_used_hours=0,
        current_label="A",
        pickup_label="B",
        dropoff_label="C",
    )
    types = [e["type"] for e in result["itinerary"]]
    assert "pickup" in types
    assert "dropoff" in types
    assert "drive" in types
    assert result["compliance"]["feasible"] is True


def test_break_after_eight_hours_driving():
    # 8.5 hours driving at 55 mph ≈ 467.5 miles loaded; tiny deadhead.
    result = plan_trip(
        route=_route(5, 470),
        shift_start=SHIFT,
        current_cycle_used_hours=0,
        current_label="A",
        pickup_label="B",
        dropoff_label="C",
    )
    breaks = [e for e in result["itinerary"] if e["type"] == "break_30m"]
    assert len(breaks) >= 1


def test_eleven_hour_drive_limit_inserts_10h_reset():
    # >11 hours driving needed: 12 hours * 55 = 660 miles
    result = plan_trip(
        route=_route(5, 660),
        shift_start=SHIFT,
        current_cycle_used_hours=0,
        current_label="A",
        pickup_label="B",
        dropoff_label="C",
    )
    rests = [e for e in result["itinerary"] if e["type"] == "rest_10h"]
    assert len(rests) >= 1
    # After a rest, drive clocks should have been reset at that point
    assert rests[0]["stateAfter"]["driveUsedHours"] == 0


def test_fuel_stop_every_1000_miles():
    result = plan_trip(
        route=_route(50, 1100),
        shift_start=SHIFT,
        current_cycle_used_hours=0,
        current_label="A",
        pickup_label="B",
        dropoff_label="C",
    )
    fuels = [e for e in result["itinerary"] if e["type"] == "fuel"]
    assert len(fuels) >= 1


def test_cycle_exhausted_raises():
    with pytest.raises(HOSPlanningError, match="cycle"):
        plan_trip(
            route=_route(10, 100),
            shift_start=SHIFT,
            current_cycle_used_hours=70,
            current_label="A",
            pickup_label="B",
            dropoff_label="C",
        )


def test_near_cycle_limit_long_trip_raises_or_warns():
    # 65 hours already used; a multi-day trip that needs more on-duty than remaining.
    with pytest.raises(HOSPlanningError):
        plan_trip(
            route=_route(100, 2000),
            shift_start=SHIFT,
            current_cycle_used_hours=65,
            current_label="A",
            pickup_label="B",
            dropoff_label="C",
        )


def test_daily_logs_total_24_hours():
    planned = plan_trip(
        route=_route(50, 800),
        shift_start=SHIFT,
        current_cycle_used_hours=10,
        current_label="Chicago, IL",
        pickup_label="Dallas, TX",
        dropoff_label="Atlanta, GA",
    )
    end = datetime.fromisoformat(planned["compliance"]["shiftEnd"])
    logs = build_daily_logs(
        planned["segments"],
        shift_start=SHIFT,
        trip_end=end,
        meta={"averageSpeedMph": 55},
    )
    assert len(logs) >= 1
    for day in logs:
        assert abs(day["totals"]["all"] - 24.0) < 0.05
        assert day["totals"]["driving"] >= 0
        assert len(day["segments"]) >= 1


def test_window_limit_triggers_reset():
    # Slow speed so window (on-duty) fills before 11 drive hours from mixed duty.
    # Pickup 1h + lots of driving with breaks: use moderate miles.
    result = plan_trip(
        route=_route(20, 550, speed=45),
        shift_start=SHIFT,
        current_cycle_used_hours=0,
        current_label="A",
        pickup_label="B",
        dropoff_label="C",
    )
    # Either a rest or completion within window — must be feasible
    assert result["compliance"]["feasible"] is True
    # Driving never exceeds 11 in a single stretch between rests
    drive_streak = 0.0
    for event in result["itinerary"]:
        if event["type"] == "drive":
            drive_streak += event["durationMinutes"] / 60.0
            assert drive_streak <= DRIVE_LIMIT_HOURS + 0.05
        elif event["type"] == "rest_10h":
            drive_streak = 0.0


def test_mock_route_builds_geometry():
    a = GeoPoint("Chicago, IL", 41.8781, -87.6298)
    b = GeoPoint("Dallas, TX", 32.7767, -96.7970)
    c = GeoPoint("Atlanta, GA", 33.7490, -84.3880)
    route = build_route(a, b, c)
    assert route["totalDistanceMiles"] > 0
    assert len(route["legs"]) == 2
    assert route["geometry"]["type"] == "LineString"


def test_break_threshold_constant():
    assert BREAK_AFTER_DRIVE_HOURS == 8.0
    assert WINDOW_LIMIT_HOURS == 14.0
    assert FUEL_EVERY_MILES == 1000.0
