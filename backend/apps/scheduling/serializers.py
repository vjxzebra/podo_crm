from datetime import UTC, timedelta
from typing import Any

from rest_framework import serializers


class UTCDateTimeField(serializers.DateTimeField):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("default_timezone", UTC)
        super().__init__(**kwargs)


class CalendarFilterSerializer(serializers.Serializer[Any]):
    specialist_id = serializers.IntegerField(required=False, min_value=1)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["from"] = serializers.DateTimeField()
        self.fields["to"] = serializers.DateTimeField()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        range_start = attrs["from"]
        range_end = attrs["to"]
        if range_start >= range_end:
            raise serializers.ValidationError({"to": "Кінець діапазону має бути пізніше початку."})
        if range_end - range_start > timedelta(days=8):
            raise serializers.ValidationError(
                {"to": "Календар можна завантажити максимум на 7 днів."}
            )
        return attrs


class SpecialistSummarySerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    display_name = serializers.CharField()


class RoomSummarySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()


class CalendarPatientSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    display_name = serializers.CharField()


class CalendarServiceSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    color = serializers.CharField()


class CalendarStatusSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    color = serializers.CharField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["label"] = serializers.CharField()


class CalendarEventSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    starts_at = UTCDateTimeField()
    ends_at = UTCDateTimeField()
    duration_minutes = serializers.IntegerField(min_value=1)
    patient = CalendarPatientSerializer()
    service = CalendarServiceSerializer()
    specialist = SpecialistSummarySerializer()
    room = RoomSummarySerializer()
    status = CalendarStatusSerializer()


class CalendarBreakSerializer(serializers.Serializer[Any]):
    starts_at = UTCDateTimeField()
    ends_at = UTCDateTimeField()


class CalendarDaySerializer(serializers.Serializer[Any]):
    date = serializers.DateField()
    is_working = serializers.BooleanField()
    starts_at = UTCDateTimeField(allow_null=True)
    ends_at = UTCDateTimeField(allow_null=True)
    breaks = CalendarBreakSerializer(many=True)


class CalendarRangeSerializer(serializers.Serializer[Any]):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["from"] = UTCDateTimeField()
        self.fields["to"] = UTCDateTimeField()


class CalendarResponseSerializer(serializers.Serializer[Any]):
    timezone = serializers.CharField()
    range = CalendarRangeSerializer()
    specialists = SpecialistSummarySerializer(many=True)
    days = CalendarDaySerializer(many=True)
    events = CalendarEventSerializer(many=True)


class AvailabilityFilterSerializer(serializers.Serializer[Any]):
    date = serializers.DateField()
    specialist_id = serializers.IntegerField(min_value=1)
    service_id = serializers.UUIDField()
    room_id = serializers.UUIDField(required=False)


class AvailabilityServiceSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    duration_minutes = serializers.IntegerField(min_value=1)


class AvailabilitySlotSerializer(serializers.Serializer[Any]):
    starts_at = UTCDateTimeField()
    ends_at = UTCDateTimeField()
    rooms = RoomSummarySerializer(many=True)


class AvailabilityResponseSerializer(serializers.Serializer[Any]):
    timezone = serializers.CharField()
    date = serializers.DateField()
    specialist = SpecialistSummarySerializer()
    service = AvailabilityServiceSerializer()
    requested_room = RoomSummarySerializer(allow_null=True)
    step_minutes = serializers.IntegerField(min_value=1)
    slots = AvailabilitySlotSerializer(many=True)


class AppointmentCreateSerializer(serializers.Serializer[Any]):
    patient_id = serializers.UUIDField()
    specialist_id = serializers.IntegerField(min_value=1)
    service_id = serializers.UUIDField()
    room_id = serializers.UUIDField()
    starts_at = serializers.DateTimeField()
    complaints = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    has_no_complaints = serializers.BooleanField(required=False, default=False)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    status_code = serializers.ChoiceField(choices=("NEW",), required=False, default="NEW")

    def validate_complaints(self, value: str) -> str:
        return value.strip()

    def validate_comment(self, value: str) -> str:
        return value.strip()


class AppointmentPatientSerializer(CalendarPatientSerializer):
    phone = serializers.CharField()


class AppointmentServiceSerializer(CalendarServiceSerializer):
    code = serializers.CharField()


class AppointmentResponseSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    starts_at = UTCDateTimeField()
    ends_at = UTCDateTimeField()
    duration_minutes = serializers.IntegerField(min_value=1)
    patient = AppointmentPatientSerializer()
    service = AppointmentServiceSerializer()
    specialist = SpecialistSummarySerializer()
    room = RoomSummarySerializer()
    status = CalendarStatusSerializer()
    complaints = serializers.CharField(allow_blank=True)
    has_no_complaints = serializers.BooleanField()
    comment = serializers.CharField(allow_blank=True)
    cancellation_reason = serializers.CharField(allow_blank=True)
    version = serializers.IntegerField(min_value=1)
    created_at = UTCDateTimeField()
    updated_at = UTCDateTimeField()


class AppointmentDetailResponseSerializer(AppointmentResponseSerializer):
    allowed_status_transitions = CalendarStatusSerializer(many=True)
    can_edit = serializers.BooleanField()
    can_reschedule = serializers.BooleanField()
    can_cancel = serializers.BooleanField()
    can_start_visit = serializers.BooleanField()
    visit_id = serializers.UUIDField(allow_null=True)


class AppointmentUpdateSerializer(serializers.Serializer[Any]):
    version = serializers.IntegerField(min_value=1)
    specialist_id = serializers.IntegerField(min_value=1, required=False)
    service_id = serializers.UUIDField(required=False)
    room_id = serializers.UUIDField(required=False)
    starts_at = serializers.DateTimeField(required=False)
    complaints = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    has_no_complaints = serializers.BooleanField(required=False)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=4000)

    def validate_complaints(self, value: str) -> str:
        return value.strip()

    def validate_comment(self, value: str) -> str:
        return value.strip()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if len(attrs) == 1:
            raise serializers.ValidationError({"non_field_errors": ["Укажіть хоча б одну зміну."]})
        return attrs


class AppointmentStatusTransitionSerializer(serializers.Serializer[Any]):
    version = serializers.IntegerField(min_value=1)
    status_code = serializers.ChoiceField(
        choices=(
            "NEW",
            "PENDING_CONFIRMATION",
            "CONFIRMED",
            "ARRIVED",
            "IN_PROGRESS",
            "COMPLETED",
            "CANCELED",
            "NO_SHOW",
        )
    )


class AppointmentCancelSerializer(serializers.Serializer[Any]):
    version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=1000)

    def validate_reason(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Укажіть причину скасування.")
        return value
