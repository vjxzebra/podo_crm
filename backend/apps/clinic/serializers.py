import re
from typing import Any

from rest_framework import serializers

from apps.clinic.models import (
    AppointmentStatusConfig,
    ClinicBreak,
    ClinicProfile,
    ClinicWorkday,
    Room,
    Service,
)

SERVICE_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]*$")
SERVICE_COLOR_PATTERN = re.compile(r"^#[0-9A-F]{6}$")
WEEKDAYS = tuple(range(7))


class ClinicProfileSerializer(serializers.ModelSerializer):
    has_logo = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = ClinicProfile
        fields = (
            "name",
            "phone",
            "email",
            "address",
            "description",
            "has_logo",
            "logo_url",
            "logo_content_type",
            "logo_size",
            "version",
            "updated_at",
        )

    def get_has_logo(self, profile: ClinicProfile) -> bool:
        return bool(profile.logo_object_key)

    def get_logo_url(self, profile: ClinicProfile) -> str | None:
        if not profile.logo_object_key:
            return None
        return f"/api/v1/clinic-profile/logo?v={profile.version}"


class ClinicProfileUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160, allow_blank=False, required=False)
    phone = serializers.CharField(max_length=32, allow_blank=False, required=False)
    email = serializers.EmailField(max_length=254, required=False)
    address = serializers.CharField(max_length=255, allow_blank=False, required=False)
    description = serializers.CharField(max_length=1000, allow_blank=True, required=False)
    version = serializers.IntegerField(min_value=1)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if len(attrs) == 1:
            raise serializers.ValidationError("Укажіть хоча б одну зміну.")
        return attrs


class ClinicLogoUploadSerializer(serializers.Serializer):
    logo = serializers.FileField()
    version = serializers.IntegerField(min_value=1)


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ("id", "name", "is_active", "version", "created_at", "updated_at")


class RoomListSerializer(serializers.Serializer):
    rooms = RoomSerializer(many=True)


class RoomCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, allow_blank=False)
    is_active = serializers.BooleanField(default=True)


class RoomUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, allow_blank=False, required=False)
    is_active = serializers.BooleanField(required=False)
    version = serializers.IntegerField(min_value=1)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if len(attrs) == 1:
            raise serializers.ValidationError("Укажіть хоча б одну зміну.")
        return attrs


class ServicePickerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ("id", "code", "name", "duration_minutes", "price_minor", "color")


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = (
            "id",
            "code",
            "name",
            "duration_minutes",
            "price_minor",
            "color",
            "is_active",
            "version",
            "created_at",
            "updated_at",
        )


class ServiceListSerializer(serializers.Serializer):
    services = ServiceSerializer(many=True)


class ServiceFilterSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)
    status = serializers.ChoiceField(
        required=False,
        choices=["all", "active", "inactive"],
        default="all",
    )


class ServiceWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32, allow_blank=False, required=False)
    name = serializers.CharField(max_length=160, allow_blank=False, required=False)
    duration_minutes = serializers.IntegerField(min_value=1, max_value=1440, required=False)
    price_minor = serializers.IntegerField(min_value=0, required=False)
    color = serializers.CharField(max_length=7, allow_blank=False, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate_code(self, value: str) -> str:
        normalized = value.strip().upper()
        if not SERVICE_CODE_PATTERN.fullmatch(normalized):
            raise serializers.ValidationError(
                "Код може містити латинські літери, цифри, дефіс і підкреслення."
            )
        return normalized

    def validate_name(self, value: str) -> str:
        return value.strip()

    def validate_color(self, value: str) -> str:
        normalized = value.strip().upper()
        if not SERVICE_COLOR_PATTERN.fullmatch(normalized):
            raise serializers.ValidationError("Укажіть колір у форматі #RRGGBB.")
        return normalized


class ServiceCreateSerializer(ServiceWriteSerializer):
    code = serializers.CharField(max_length=32, allow_blank=False)
    name = serializers.CharField(max_length=160, allow_blank=False)
    duration_minutes = serializers.IntegerField(min_value=1, max_value=1440)
    price_minor = serializers.IntegerField(min_value=0)
    color = serializers.CharField(max_length=7, allow_blank=False)
    is_active = serializers.BooleanField(default=True)


class ServiceUpdateSerializer(ServiceWriteSerializer):
    version = serializers.IntegerField(min_value=1)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if len(attrs) == 1:
            raise serializers.ValidationError("Укажіть хоча б одну зміну.")
        return attrs


class AppointmentStatusConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppointmentStatusConfig
        fields = (
            "code",
            "label",
            "color",
            "manual_admin",
            "manual_reception",
            "manual_podologist",
            "version",
            "updated_at",
        )


class AppointmentStatusConfigListSerializer(serializers.Serializer):
    statuses = AppointmentStatusConfigSerializer(many=True)


class AppointmentStatusConfigUpdateSerializer(serializers.Serializer):
    label = serializers.CharField(  # type: ignore[assignment]
        max_length=80, allow_blank=False, required=False
    )
    color = serializers.CharField(max_length=7, allow_blank=False, required=False)
    manual_admin = serializers.BooleanField(required=False)
    manual_reception = serializers.BooleanField(required=False)
    manual_podologist = serializers.BooleanField(required=False)
    version = serializers.IntegerField(min_value=1)

    def validate_label(self, value: str) -> str:
        return value.strip()

    def validate_color(self, value: str) -> str:
        normalized = value.strip().upper()
        if not SERVICE_COLOR_PATTERN.fullmatch(normalized):
            raise serializers.ValidationError("Укажіть колір у форматі #RRGGBB.")
        return normalized

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if len(attrs) == 1:
            raise serializers.ValidationError("Укажіть хоча б одну зміну.")
        return attrs


class ClinicBreakSerializer(serializers.ModelSerializer):
    start_time = serializers.TimeField(format="%H:%M")
    end_time = serializers.TimeField(format="%H:%M")

    class Meta:
        model = ClinicBreak
        fields = ("id", "start_time", "end_time")


class ClinicWorkdaySerializer(serializers.ModelSerializer):
    start_time = serializers.TimeField(format="%H:%M", allow_null=True)
    end_time = serializers.TimeField(format="%H:%M", allow_null=True)
    breaks = ClinicBreakSerializer(many=True)

    class Meta:
        model = ClinicWorkday
        fields = (
            "weekday",
            "is_working",
            "start_time",
            "end_time",
            "breaks",
            "version",
            "updated_at",
        )


class ClinicWorkdayListSerializer(serializers.Serializer):
    timezone = serializers.CharField()
    workdays = ClinicWorkdaySerializer(many=True)


class ClinicBreakWriteSerializer(serializers.Serializer):
    start_time = serializers.TimeField(input_formats=["%H:%M", "%H:%M:%S"])
    end_time = serializers.TimeField(input_formats=["%H:%M", "%H:%M:%S"])

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError("Завершення перерви має бути пізніше за початок.")
        return attrs


class ClinicWorkdayWriteSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    is_working = serializers.BooleanField()
    start_time = serializers.TimeField(
        required=False,
        allow_null=True,
        input_formats=["%H:%M", "%H:%M:%S"],
    )
    end_time = serializers.TimeField(
        required=False,
        allow_null=True,
        input_formats=["%H:%M", "%H:%M:%S"],
    )
    breaks = ClinicBreakWriteSerializer(many=True, default=list)
    version = serializers.IntegerField(min_value=1)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        breaks = attrs.get("breaks", [])
        if not attrs["is_working"]:
            if start_time is not None or end_time is not None or breaks:
                raise serializers.ValidationError(
                    "Вихідний день не може містити робочі години або перерви."
                )
            return attrs
        if start_time is None or end_time is None:
            raise serializers.ValidationError("Для робочого дня вкажіть початок і завершення.")
        if end_time <= start_time:
            raise serializers.ValidationError(
                "Завершення робочого дня має бути пізніше за початок."
            )
        ordered_breaks = sorted(breaks, key=lambda item: item["start_time"])
        previous_end = None
        for item in ordered_breaks:
            if item["start_time"] < start_time or item["end_time"] > end_time:
                raise serializers.ValidationError("Перерви мають бути всередині робочого дня.")
            if previous_end is not None and item["start_time"] < previous_end:
                raise serializers.ValidationError("Перерви не можуть накладатися одна на одну.")
            previous_end = item["end_time"]
        attrs["breaks"] = ordered_breaks
        return attrs


class ClinicScheduleUpdateSerializer(serializers.Serializer):
    workdays = ClinicWorkdayWriteSerializer(many=True)

    def validate_workdays(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        weekdays = [item["weekday"] for item in value]
        if len(value) != 7 or set(weekdays) != set(WEEKDAYS):
            raise serializers.ValidationError(
                "Передайте рівно сім унікальних днів тижня від 0 до 6."
            )
        return sorted(value, key=lambda item: item["weekday"])
