from rest_framework import serializers


class TripPlanRequestSerializer(serializers.Serializer):
    currentLocation = serializers.CharField(max_length=512, trim_whitespace=True)
    pickupLocation = serializers.CharField(max_length=512, trim_whitespace=True)
    dropoffLocation = serializers.CharField(max_length=512, trim_whitespace=True)
    currentCycleUsedHours = serializers.FloatField(min_value=0.0, max_value=70.0)
    shiftStart = serializers.DateTimeField(required=False, allow_null=True)

    def validate_currentLocation(self, value: str) -> str:
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Current location is required.")
        return value.strip()

    def validate_pickupLocation(self, value: str) -> str:
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Pickup location is required.")
        return value.strip()

    def validate_dropoffLocation(self, value: str) -> str:
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Dropoff location is required.")
        return value.strip()
