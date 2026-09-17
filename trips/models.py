import uuid

from django.db import models


class TripPlan(models.Model):
    """Persisted trip plan with immutable calculation inputs and results."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    current_location = models.CharField(max_length=512)
    pickup_location = models.CharField(max_length=512)
    dropoff_location = models.CharField(max_length=512)
    current_cycle_used_hours = models.DecimalField(max_digits=5, decimal_places=2)
    shift_start = models.DateTimeField()

    calculation_version = models.CharField(max_length=64)
    route = models.JSONField(default=dict)
    itinerary = models.JSONField(default=list)
    compliance = models.JSONField(default=dict)
    logs = models.JSONField(default=list)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"TripPlan {self.id} ({self.pickup_location} → {self.dropoff_location})"
