from typing import Any

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
from apps.patients.models import Patient
from apps.work_items.models import WorkItem, WorkItemKind


class WorkItemAssigneeSerializer(serializers.ModelSerializer[User]):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "display_name", "role")


class WorkItemPatientSerializer(serializers.ModelSerializer[Patient]):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Patient
        fields = ("id", "public_number", "display_name", "phone")


class WorkItemSerializer(serializers.ModelSerializer[WorkItem]):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    assignee = WorkItemAssigneeSerializer(read_only=True)
    patient = WorkItemPatientSerializer(read_only=True, allow_null=True)
    completed_by = WorkItemAssigneeSerializer(read_only=True, allow_null=True)
    created_by = WorkItemAssigneeSerializer(read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = WorkItem
        fields = (
            "id",
            "kind",
            "kind_label",
            "title",
            "due_at",
            "assignee",
            "patient",
            "comment",
            "is_important",
            "is_completed",
            "is_overdue",
            "completed_at",
            "completed_by",
            "version",
            "created_by",
            "created_at",
            "updated_at",
        )

    @extend_schema_field(serializers.BooleanField())
    def get_is_overdue(self, item: WorkItem) -> bool:
        return not item.is_completed and item.due_at < timezone.now()


class WorkItemSummarySerializer(serializers.Serializer[Any]):
    open = serializers.IntegerField(min_value=0)
    completed = serializers.IntegerField(min_value=0)
    overdue = serializers.IntegerField(min_value=0)
    important = serializers.IntegerField(min_value=0)


class WorkItemListResponseSerializer(serializers.Serializer[Any]):
    work_items = WorkItemSerializer(many=True)
    summary = WorkItemSummarySerializer()
    assignees = WorkItemAssigneeSerializer(many=True)
    effective_scope = serializers.ChoiceField(choices=("own", "all"))


class WorkItemFilterSerializer(serializers.Serializer[Any]):
    scope = serializers.ChoiceField(
        choices=("own", "all"),
        required=False,
        default="own",
    )
    status = serializers.ChoiceField(
        choices=("open", "completed", "all"),
        required=False,
        default="open",
    )
    search = serializers.CharField(required=False, allow_blank=True, max_length=120)


class WorkItemCreateSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=WorkItemKind.choices)
    title = serializers.CharField(max_length=200)
    due_at = serializers.DateTimeField()
    assignee_id = serializers.IntegerField(min_value=1)
    patient_id = serializers.UUIDField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    is_important = serializers.BooleanField(required=False, default=False)

    def validate_title(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Укажіть назву справи.")
        return value

    def validate_comment(self, value: str) -> str:
        return value.strip()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["kind"] == WorkItemKind.CALLBACK and attrs.get("patient_id") is None:
            raise serializers.ValidationError(
                {"patient_id": ["Для справи «Перетелефонувати» оберіть пацієнта."]}
            )
        return attrs


class WorkItemUpdateSerializer(serializers.Serializer[Any]):
    version = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(choices=WorkItemKind.choices, required=False)
    title = serializers.CharField(max_length=200, required=False)
    due_at = serializers.DateTimeField(required=False)
    assignee_id = serializers.IntegerField(min_value=1, required=False)
    patient_id = serializers.UUIDField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    is_important = serializers.BooleanField(required=False)
    is_completed = serializers.BooleanField(required=False)

    def validate_title(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Укажіть назву справи.")
        return value

    def validate_comment(self, value: str) -> str:
        return value.strip()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if len(attrs) == 1:
            raise serializers.ValidationError({"non_field_errors": ["Укажіть хоча б одну зміну."]})
        return attrs
