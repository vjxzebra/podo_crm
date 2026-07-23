from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.billing.models import ReceivableStatus
from apps.visits.models import (
    DetectedCondition,
    VisitPhotoKind,
    VisitPhotoPreviewStatus,
    VisitStatus,
)


class StartVisitSerializer(serializers.Serializer[Any]):
    version = serializers.IntegerField(min_value=1)


class VisitServiceLineInputSerializer(serializers.Serializer[Any]):
    service_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=99)


class VisitMaterialLineInputSerializer(serializers.Serializer[Any]):
    lot_id = serializers.UUIDField()
    quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )


class VisitDraftUpdateSerializer(serializers.Serializer[Any]):
    version = serializers.IntegerField(min_value=1)
    complaints = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    has_no_complaints = serializers.BooleanField(required=False)
    objective_examination = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=10000,
    )
    detected_conditions = serializers.ListField(
        child=serializers.ChoiceField(choices=DetectedCondition.choices),
        required=False,
        allow_empty=True,
        max_length=len(DetectedCondition.values),
    )
    podologist_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=10000,
    )
    service_lines = serializers.ListField(
        child=VisitServiceLineInputSerializer(),
        required=False,
        allow_empty=True,
        max_length=50,
    )
    material_lines = serializers.ListField(
        child=VisitMaterialLineInputSerializer(),
        required=False,
        allow_empty=True,
        max_length=100,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if set(attrs) == {"version"}:
            raise serializers.ValidationError(
                {"non_field_errors": ["Передайте хоча б одне поле чернетки."]}
            )
        return attrs


class VisitPatientSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    display_name = serializers.CharField()


class VisitSpecialistSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    display_name = serializers.CharField()


class VisitAppointmentSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    service_name = serializers.CharField()
    room_name = serializers.CharField()
    status_code = serializers.CharField()
    status_label = serializers.CharField()


class VisitServiceLineSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    service_id = serializers.UUIDField()
    service_code = serializers.CharField()
    service_name = serializers.CharField()
    duration_minutes = serializers.IntegerField()
    price_minor = serializers.IntegerField()
    quantity = serializers.IntegerField()
    is_primary = serializers.BooleanField()
    line_total_minor = serializers.IntegerField()


class VisitMaterialLineSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    material_id = serializers.UUIDField()
    lot_id = serializers.UUIDField()
    material_sku = serializers.CharField()
    material_name = serializers.CharField()
    material_unit = serializers.CharField()
    lot_number = serializers.CharField()
    expires_on = serializers.DateField(allow_null=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    available_quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    is_available = serializers.BooleanField()


class VisitPhotoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    visit_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=VisitPhotoKind.choices)
    content_type = serializers.CharField()
    size = serializers.IntegerField()
    width = serializers.IntegerField()
    height = serializers.IntegerField()
    original_name = serializers.CharField()
    preview_status = serializers.ChoiceField(choices=VisitPhotoPreviewStatus.choices)
    created_by_id = serializers.IntegerField()
    created_by_name = serializers.CharField()
    created_at = serializers.DateTimeField()
    image_url = serializers.CharField()
    preview_url = serializers.CharField(allow_null=True)


class VisitRecommendationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    author_id = serializers.IntegerField()
    author_name = serializers.CharField()
    text = serializers.CharField()
    version = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class VisitRecommendationCreateSerializer(serializers.Serializer[Any]):
    text = serializers.CharField(max_length=10000, trim_whitespace=True)


class VisitRecommendationUpdateSerializer(VisitRecommendationCreateSerializer):
    version = serializers.IntegerField(min_value=1)


class VisitResponseSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    status = serializers.ChoiceField(choices=VisitStatus.choices)
    version = serializers.IntegerField()
    appointment = VisitAppointmentSerializer()
    patient = VisitPatientSerializer()
    specialist = VisitSpecialistSerializer()
    complaints = serializers.CharField(allow_blank=True)
    has_no_complaints = serializers.BooleanField()
    objective_examination = serializers.CharField(allow_blank=True)
    detected_conditions = serializers.ListField(
        child=serializers.ChoiceField(choices=DetectedCondition.choices)
    )
    podologist_notes = serializers.CharField(allow_blank=True)
    total_minor = serializers.IntegerField(allow_null=True)
    payment_handoff_requested = serializers.BooleanField()
    service_lines = VisitServiceLineSerializer(many=True)
    material_lines = VisitMaterialLineSerializer(many=True)
    services_total_minor = serializers.IntegerField()
    photos = VisitPhotoSerializer(many=True)
    recommendations = VisitRecommendationSerializer(many=True)
    editable = serializers.BooleanField()
    started_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)


class VisitMaterialOptionQuerySerializer(serializers.Serializer[Any]):
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)


class VisitMaterialLotOptionSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    lot_number = serializers.CharField()
    expires_on = serializers.DateField(allow_null=True)
    current_quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    fefo_rank = serializers.IntegerField()


class VisitMaterialOptionSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    sku = serializers.CharField()
    name = serializers.CharField()
    unit = serializers.CharField()
    available_quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    lots = VisitMaterialLotOptionSerializer(many=True)


class VisitMaterialOptionListSerializer(serializers.Serializer[Any]):
    materials = VisitMaterialOptionSerializer(many=True)


class VisitPhotoIntentCreateSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=VisitPhotoKind.choices)


class VisitPhotoUploadIntentSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    visit_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=VisitPhotoKind.choices)
    expires_at = serializers.DateTimeField()
    max_bytes = serializers.IntegerField()
    allowed_content_types = serializers.ListField(child=serializers.CharField())
    finalize_url = serializers.CharField()


class VisitPhotoFinalizeSerializer(serializers.Serializer[Any]):
    intent_id = serializers.UUIDField()
    photo = serializers.FileField()


class VisitPhotoContentQuerySerializer(serializers.Serializer[Any]):
    token = serializers.CharField(max_length=2000)


class VisitFollowUpInputSerializer(serializers.Serializer[Any]):
    starts_at = serializers.DateTimeField()
    service_id = serializers.UUIDField()
    specialist_id = serializers.IntegerField(min_value=1)
    room_id = serializers.UUIDField()


class VisitFinishSerializer(serializers.Serializer[Any]):
    version = serializers.IntegerField(min_value=1)
    recommendations = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=10000,
        trim_whitespace=True,
    )
    payment_handoff_requested = serializers.BooleanField()
    follow_up = VisitFollowUpInputSerializer(required=False, allow_null=True, default=None)


class VisitReceivableSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    amount_minor = serializers.IntegerField(min_value=0)
    status = serializers.ChoiceField(choices=ReceivableStatus.choices)
    created_at = serializers.DateTimeField()


class VisitFinishResponseSerializer(serializers.Serializer[Any]):
    replayed = serializers.BooleanField()
    visit = VisitResponseSerializer()
    receivable = VisitReceivableSerializer()
    inventory_operation_id = serializers.UUIDField(allow_null=True)
    movement_ids = serializers.ListField(child=serializers.UUIDField())
    follow_up_appointment_id = serializers.UUIDField(allow_null=True)
