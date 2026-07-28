from typing import Any

from rest_framework import serializers

from apps.booking_requests.models import (
    BookingRequest,
    BookingRequestApiCredential,
    BookingRequestSource,
    BookingRequestStatus,
)
from apps.patients.normalization import InvalidPhoneError, normalize_phone


class BookingRequestSerializer(serializers.ModelSerializer[BookingRequest]):
    source_label = serializers.CharField(source="get_source_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = BookingRequest
        fields = (
            "id",
            "public_number",
            "source",
            "source_label",
            "status",
            "status_label",
            "client_name",
            "phone",
            "service",
            "contact_handle",
            "message",
            "preferred_at",
            "external_reference",
            "processed_by_display_name",
            "processed_at",
            "version",
            "created_at",
            "updated_at",
        )


class BookingRequestCountsSerializer(serializers.Serializer[Any]):
    new = serializers.IntegerField(min_value=0)
    processed = serializers.IntegerField(min_value=0)
    total = serializers.IntegerField(min_value=0)


class BookingRequestListResponseSerializer(serializers.Serializer[Any]):
    booking_requests = BookingRequestSerializer(many=True)
    counts = BookingRequestCountsSerializer()
    next_cursor = serializers.CharField(allow_null=True)


class BookingRequestFilterSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(
        choices=("ALL", *BookingRequestStatus.values),
        default=BookingRequestStatus.NEW,
        required=False,
    )
    source = serializers.ChoiceField(  # type: ignore[assignment]
        choices=("ALL", *BookingRequestSource.values),
        default="ALL",
        required=False,
    )
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
    )
    cursor = serializers.CharField(required=False, allow_blank=False, max_length=500)


class BookingRequestProcessSerializer(serializers.Serializer[Any]):
    version = serializers.IntegerField(min_value=1)

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if isinstance(data, dict):
            unknown_fields = set(data) - {"version"}
            if unknown_fields:
                raise serializers.ValidationError(
                    {field: ["Невідоме поле."] for field in sorted(unknown_fields)}
                )
        return super().to_internal_value(data)


class StrictFieldsSerializer(serializers.Serializer[Any]):
    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if isinstance(data, dict):
            unknown_fields = set(data) - set(self.fields)
            if unknown_fields:
                raise serializers.ValidationError(
                    {field: ["Невідоме поле."] for field in sorted(unknown_fields)}
                )
        return super().to_internal_value(data)


class BookingRequestApiCredentialSerializer(
    serializers.ModelSerializer[BookingRequestApiCredential]
):
    is_configured = serializers.BooleanField(read_only=True)

    class Meta:
        model = BookingRequestApiCredential
        fields = (
            "is_configured",
            "token_hint",
            "rotated_at",
            "rotated_by_display_name",
            "version",
        )


class BookingRequestApiCredentialRotateSerializer(StrictFieldsSerializer):
    version = serializers.IntegerField(min_value=0)
    confirm = serializers.BooleanField()

    def validate_confirm(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("Підтвердіть генерацію нового токена.")
        return value


class BookingRequestApiCredentialRotatedSerializer(BookingRequestApiCredentialSerializer):
    token = serializers.CharField(read_only=True)

    class Meta:
        model = BookingRequestApiCredential
        fields = (
            "is_configured",
            "token_hint",
            "rotated_at",
            "rotated_by_display_name",
            "version",
            "token",
        )


class ExternalBookingRequestSerializer(StrictFieldsSerializer):
    source = serializers.ChoiceField(  # type: ignore[assignment]
        choices=BookingRequestSource.choices
    )
    client_name = serializers.CharField(
        allow_blank=True,
        default="",
        max_length=160,
        required=False,
        trim_whitespace=True,
    )
    phone = serializers.CharField(
        allow_blank=True,
        default="",
        max_length=32,
        required=False,
        trim_whitespace=True,
    )
    service = serializers.CharField(
        allow_blank=True,
        default="",
        max_length=160,
        required=False,
        trim_whitespace=True,
    )
    contact_handle = serializers.CharField(
        allow_blank=True,
        default="",
        max_length=100,
        required=False,
        trim_whitespace=True,
    )
    message = serializers.CharField(
        allow_blank=True,
        default="",
        max_length=2000,
        required=False,
        trim_whitespace=True,
    )
    preferred_at = serializers.DateTimeField(
        allow_null=True,
        default=None,
        required=False,
    )
    external_reference = serializers.CharField(
        allow_blank=True,
        default="",
        max_length=160,
        required=False,
        trim_whitespace=True,
    )

    def validate_phone(self, value: str) -> str:
        if not value:
            return value
        try:
            normalize_phone(value)
        except InvalidPhoneError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


class ExternalBookingRequestResponseSerializer(serializers.ModelSerializer[BookingRequest]):
    class Meta:
        model = BookingRequest
        fields = ("id", "public_number", "status", "created_at")
