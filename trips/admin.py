from django.contrib import admin

from trips.models import TripPlan


@admin.register(TripPlan)
class TripPlanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "pickup_location",
        "dropoff_location",
        "current_cycle_used_hours",
        "created_at",
    )
    readonly_fields = ("id", "created_at", "route", "itinerary", "compliance", "logs")
