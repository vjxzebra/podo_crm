from datetime import date
from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User, UserRole
from apps.patients.models import Patient, PatientMedicalProfile
from apps.patients.normalization import InvalidPhoneError, normalize_phone


class PodologistSummarySerializer(serializers.ModelSerializer[User]):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "display_name")


class PatientListItemSerializer(serializers.ModelSerializer[Patient]):
    display_name = serializers.CharField(read_only=True)
    primary_podologist = PodologistSummarySerializer(read_only=True, allow_null=True)
    appointment_summary = serializers.SerializerMethodField()
    state_label = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = (
            "id",
            "public_number",
            "first_name",
            "last_name",
            "display_name",
            "phone",
            "birth_date",
            "email",
            "primary_podologist",
            "appointment_summary",
            "state_label",
            "created_at",
        )

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_appointment_summary(self, patient: Patient) -> None:
        return None

    @extend_schema_field(serializers.CharField())
    def get_state_label(self, patient: Patient) -> str:
        return "Новий пацієнт"


class PatientSerializer(PatientListItemSerializer):
    class Meta:
        model = Patient
        fields = (*PatientListItemSerializer.Meta.fields, "note", "updated_at")


class PatientAppointmentSummarySerializer(serializers.Serializer[Any]):
    starts_at = serializers.DateTimeField()
    status = serializers.CharField()
    service = serializers.CharField()
    specialist = serializers.CharField()
    room = serializers.CharField(allow_blank=True)
    cost_minor = serializers.IntegerField(min_value=0)


class PatientVisitHistoryItemSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    occurred_at = serializers.DateTimeField()
    status = serializers.CharField()
    services = serializers.ListField(child=serializers.CharField())
    specialist = serializers.CharField()
    summary = serializers.CharField(allow_blank=True)
    cost_minor = serializers.IntegerField(min_value=0)
    has_photos = serializers.BooleanField()


class PatientPhotoVisitMetadataSerializer(serializers.Serializer[Any]):
    visit_id = serializers.UUIDField()
    occurred_at = serializers.DateTimeField()
    caption = serializers.CharField(allow_blank=True)
    before_count = serializers.IntegerField(min_value=0)
    after_count = serializers.IntegerField(min_value=0)


class PatientMedicalProfileSerializer(serializers.ModelSerializer[PatientMedicalProfile]):
    class Meta:
        model = PatientMedicalProfile
        fields = ("allergies", "chronic_conditions", "notes", "updated_at")


class PatientDetailBaseSerializer(PatientSerializer):
    age = serializers.SerializerMethodField()
    service_started_at = serializers.DateTimeField(source="created_at", read_only=True)
    projection = serializers.SerializerMethodField()
    upcoming_appointment = serializers.SerializerMethodField()
    visit_history = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = (
            *PatientSerializer.Meta.fields,
            "age",
            "service_started_at",
            "projection",
            "upcoming_appointment",
            "visit_history",
        )

    @extend_schema_field(serializers.IntegerField(allow_null=True, min_value=0))
    def get_age(self, patient: Patient) -> int | None:
        if patient.birth_date is None:
            return None
        today = date.today()
        return (
            today.year
            - patient.birth_date.year
            - ((today.month, today.day) < (patient.birth_date.month, patient.birth_date.day))
        )

    @extend_schema_field(serializers.CharField())
    def get_projection(self, patient: Patient) -> str:
        return "reception"

    @extend_schema_field(PatientAppointmentSummarySerializer(allow_null=True))
    def get_upcoming_appointment(self, patient: Patient) -> None:
        # Scheduling packets will populate this projection.
        return None

    @extend_schema_field(PatientVisitHistoryItemSerializer(many=True))
    def get_visit_history(self, patient: Patient) -> list[dict[str, Any]]:
        # Visit packets will populate role-specific history rows.
        return []


class ReceptionPatientDetailSerializer(PatientDetailBaseSerializer):
    """Safe contact/administrative projection with no medical keys."""


class MedicalPatientDetailSerializer(PatientDetailBaseSerializer):
    medical_profile = serializers.SerializerMethodField()
    photo_archive = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = (
            *PatientDetailBaseSerializer.Meta.fields,
            "medical_profile",
            "photo_archive",
        )

    @extend_schema_field(PatientMedicalProfileSerializer())
    def get_medical_profile(self, patient: Patient) -> dict[str, Any]:
        profile = getattr(patient, "medical_profile", None)
        if profile is None:
            return {
                "allergies": [],
                "chronic_conditions": [],
                "notes": "",
                "updated_at": patient.updated_at,
            }
        return dict(PatientMedicalProfileSerializer(profile).data)

    @extend_schema_field(PatientPhotoVisitMetadataSerializer(many=True))
    def get_photo_archive(self, patient: Patient) -> list[dict[str, Any]]:
        # TP-603/TP-605 will populate private visit-photo metadata.
        return []

    @extend_schema_field(serializers.CharField())
    def get_projection(self, patient: Patient) -> str:
        return "medical"


class PatientFilterSerializer(serializers.Serializer[Any]):
    search = serializers.CharField(required=False, allow_blank=True, max_length=120)
    cursor = serializers.CharField(required=False, allow_blank=False, max_length=512)


class PatientListResponseSerializer(serializers.Serializer[Any]):
    patients = PatientListItemSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)


class PatientCreateSerializer(serializers.Serializer[Any]):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=32)
    birth_date = serializers.DateField(required=False, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, max_length=254)
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    primary_podologist_id = serializers.PrimaryKeyRelatedField(
        source="primary_podologist",
        queryset=User.objects.filter(role=UserRole.PODOLOGIST, is_active=True),
        required=False,
        allow_null=True,
    )

    def validate_first_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Укажіть ім’я.")
        return value

    def validate_last_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Укажіть прізвище.")
        return value

    def validate_phone(self, value: str) -> str:
        value = value.strip()
        try:
            normalize_phone(value)
        except InvalidPhoneError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    def validate_birth_date(self, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise serializers.ValidationError("Дата народження не може бути в майбутньому.")
        return value


class PatientUpdateBaseSerializer(PatientCreateSerializer):
    first_name = serializers.CharField(required=False, max_length=100)
    last_name = serializers.CharField(required=False, max_length=100)
    phone = serializers.CharField(required=False, max_length=32)
    birth_date = serializers.DateField(required=False, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, max_length=254)
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    primary_podologist_id = serializers.PrimaryKeyRelatedField(
        source="primary_podologist",
        queryset=User.objects.filter(role=UserRole.PODOLOGIST, is_active=True),
        required=False,
        allow_null=True,
    )


def _normalize_medical_items(items: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = item.strip()
        if not value or value.casefold() in seen:
            continue
        normalized.append(value)
        seen.add(value.casefold())
    return normalized


class PatientMedicalProfileUpdateSerializer(serializers.Serializer[Any]):
    allergies = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        max_length=50,
    )
    chronic_conditions = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        max_length=50,
    )
    notes = serializers.CharField(required=False, allow_blank=True, max_length=4000)

    def validate_allergies(self, value: list[str]) -> list[str]:
        return _normalize_medical_items(value)

    def validate_chronic_conditions(self, value: list[str]) -> list[str]:
        return _normalize_medical_items(value)


class ReceptionPatientUpdateSerializer(PatientUpdateBaseSerializer):
    pass


class MedicalPatientUpdateSerializer(PatientUpdateBaseSerializer):
    medical_profile = PatientMedicalProfileUpdateSerializer(required=False)


class PatientCreateResponseSerializer(serializers.Serializer[Any]):
    patient = PatientSerializer()
    duplicate_warning = serializers.BooleanField()
    possible_duplicates = PatientListItemSerializer(many=True)
