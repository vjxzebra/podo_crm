import re
from typing import Any

from rest_framework import serializers

from apps.clinic.models import ClinicProfile, Room, Service

SERVICE_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]*$")
SERVICE_COLOR_PATTERN = re.compile(r"^#[0-9A-F]{6}$")


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
