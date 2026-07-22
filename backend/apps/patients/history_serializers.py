from typing import Any

from rest_framework import serializers

from apps.visits.serializers import VisitPhotoSerializer


class PatientArchiveCursorQuerySerializer(serializers.Serializer[Any]):
    cursor = serializers.CharField(required=False, allow_blank=False, max_length=2000)


class PatientHistorySpecialistSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    display_name = serializers.CharField()


class PatientHistoryServiceSerializer(serializers.Serializer[Any]):
    service_name = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    line_total_minor = serializers.IntegerField(min_value=0)


class PatientHistoryBaseItemSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField()
    status = serializers.CharField()
    status_label = serializers.CharField()
    services = PatientHistoryServiceSerializer(many=True)
    specialist = PatientHistorySpecialistSerializer()
    total_minor = serializers.IntegerField(min_value=0)


class PatientHistoryMedicalItemSerializer(PatientHistoryBaseItemSerializer):
    clinical_summary = serializers.CharField(allow_blank=True, max_length=400)
    has_photos = serializers.BooleanField()
    before_photo_count = serializers.IntegerField(min_value=0)
    after_photo_count = serializers.IntegerField(min_value=0)
    recommendations_count = serializers.IntegerField(min_value=0)


class PatientHistorySafeResponseSerializer(serializers.Serializer[Any]):
    visits = PatientHistoryBaseItemSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)


class PatientHistoryMedicalResponseSerializer(serializers.Serializer[Any]):
    visits = PatientHistoryMedicalItemSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)


class PatientPhotoArchiveVisitSerializer(PatientHistoryBaseItemSerializer):
    photos = VisitPhotoSerializer(many=True)


class PatientPhotoArchiveResponseSerializer(serializers.Serializer[Any]):
    visits = PatientPhotoArchiveVisitSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)


class RecommendationVisitSummarySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    services = serializers.ListField(child=serializers.CharField())


class RecommendationAuthorSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    display_name = serializers.CharField()


class PatientRecommendationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    visit = RecommendationVisitSummarySerializer()
    author = RecommendationAuthorSerializer()
    text = serializers.CharField()
    version = serializers.IntegerField(min_value=1)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    can_edit = serializers.BooleanField()


class PatientRecommendationResponseSerializer(serializers.Serializer[Any]):
    recommendations = PatientRecommendationSerializer(many=True)
    eligible_visits = RecommendationVisitSummarySerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)
