from django.urls import path

from trips.views import HealthView, TripPlanCreateView, TripPlanDetailView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("trips/plan/", TripPlanCreateView.as_view(), name="trip-plan-create"),
    path("trips/<uuid:trip_id>/", TripPlanDetailView.as_view(), name="trip-plan-detail"),
]
