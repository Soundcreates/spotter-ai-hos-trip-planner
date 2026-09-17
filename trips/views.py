"""API views for trip planning."""

from __future__ import annotations

from datetime import datetime, timezone

from django.conf import settings
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from trips.models import TripPlan
from trips.serializers import TripPlanRequestSerializer
from trips.services.hos import HOSPlanningError, plan_trip
from trips.services.logs import build_daily_logs
from trips.services.routing import RoutingError, build_route, geocode


def _default_shift_start() -> datetime:
    now = datetime.now(timezone.utc)
    # Next 06:00 UTC-ish local demo default: today 06:00 UTC if still early, else tomorrow.
    start = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if start <= now:
        from datetime import timedelta

        start = start + timedelta(days=1)
    return start


class TripPlanCreateView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request: Request) -> Response:
        serializer = TripPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        shift_raw = data.get("shiftStart")
        if shift_raw:
            shift_start = shift_raw
            if shift_start.tzinfo is None:
                shift_start = shift_start.replace(tzinfo=timezone.utc)
        else:
            shift_start = _default_shift_start()

        try:
            current = geocode(data["currentLocation"])
            pickup = geocode(data["pickupLocation"])
            dropoff = geocode(data["dropoffLocation"])
            route = build_route(current, pickup, dropoff)
            planned = plan_trip(
                route=route,
                shift_start=shift_start,
                current_cycle_used_hours=float(data["currentCycleUsedHours"]),
                current_label=current.label,
                pickup_label=pickup.label,
                dropoff_label=dropoff.label,
            )
        except RoutingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except HOSPlanningError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        trip_end = parse_datetime(planned["compliance"]["shiftEnd"])
        logs = build_daily_logs(
            planned["segments"],
            shift_start=shift_start,
            trip_end=trip_end or shift_start,
            meta={
                "fromLocation": data["pickupLocation"],
                "toLocation": data["dropoffLocation"],
                "averageSpeedMph": route.get("averageSpeedMph", 55),
            },
        )

        compliance = planned["compliance"]
        compliance["calculationVersion"] = getattr(
            settings, "CALCULATION_VERSION", compliance.get("calculationVersion")
        )

        trip = TripPlan.objects.create(
            current_location=data["currentLocation"],
            pickup_location=data["pickupLocation"],
            dropoff_location=data["dropoffLocation"],
            current_cycle_used_hours=data["currentCycleUsedHours"],
            shift_start=shift_start,
            calculation_version=compliance["calculationVersion"],
            route=route,
            itinerary=planned["itinerary"],
            compliance=compliance,
            logs=logs,
        )

        return Response(_serialize_trip(trip), status=status.HTTP_201_CREATED)


class TripPlanDetailView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request, trip_id) -> Response:
        try:
            trip = TripPlan.objects.get(pk=trip_id)
        except TripPlan.DoesNotExist:
            return Response({"detail": "Trip not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_trip(trip))


class HealthView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request) -> Response:
        return Response({"status": "ok", "calculationVersion": settings.CALCULATION_VERSION})


def _serialize_trip(trip: TripPlan) -> dict:
    return {
        "tripId": str(trip.id),
        "createdAt": trip.created_at.isoformat(),
        "inputs": {
            "currentLocation": trip.current_location,
            "pickupLocation": trip.pickup_location,
            "dropoffLocation": trip.dropoff_location,
            "currentCycleUsedHours": float(trip.current_cycle_used_hours),
            "shiftStart": trip.shift_start.isoformat(),
        },
        "route": trip.route,
        "itinerary": trip.itinerary,
        "compliance": trip.compliance,
        "logs": trip.logs,
    }
