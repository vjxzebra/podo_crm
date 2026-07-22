from datetime import timedelta
from typing import Any

from rest_framework import serializers


class OverviewFilterSerializer(serializers.Serializer[Any]):
    date = serializers.DateField(required=False)


class OverviewMetricSerializer(serializers.Serializer[Any]):
    key = serializers.CharField()
    value = serializers.IntegerField()
    format = serializers.ChoiceField(choices=("integer", "money", "duration"))
    note = serializers.CharField()
    tone = serializers.ChoiceField(choices=("sage", "sand", "lilac", "coral", "blue"))

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["label"] = serializers.CharField()


class OverviewPatientSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    display_name = serializers.CharField()


class OverviewSpecialistSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    display_name = serializers.CharField()


class OverviewResourceSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()


class OverviewServiceSerializer(OverviewResourceSerializer):
    color = serializers.CharField()


class OverviewStatusSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    color = serializers.CharField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["label"] = serializers.CharField()


class OverviewAppointmentSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    duration_minutes = serializers.IntegerField()
    patient = OverviewPatientSerializer()
    specialist = OverviewSpecialistSerializer()
    service = OverviewServiceSerializer()
    room = OverviewResourceSerializer()
    status = OverviewStatusSerializer()


class OverviewWorkdaySerializer(serializers.Serializer[Any]):
    is_working = serializers.BooleanField()
    starts_at = serializers.DateTimeField(allow_null=True)
    ends_at = serializers.DateTimeField(allow_null=True)
    break_minutes = serializers.IntegerField()
    net_minutes = serializers.IntegerField()


class OverviewAttentionSerializer(serializers.Serializer[Any]):
    kind = serializers.CharField()
    count = serializers.IntegerField()
    deep_link = serializers.CharField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["label"] = serializers.CharField()


class OverviewResponseSerializer(serializers.Serializer[Any]):
    role = serializers.CharField()
    date = serializers.DateField()
    timezone = serializers.CharField()
    metrics = OverviewMetricSerializer(many=True)
    schedule = OverviewAppointmentSerializer(many=True)
    next_appointment = OverviewAppointmentSerializer(allow_null=True)
    workday = OverviewWorkdaySerializer()
    attention = OverviewAttentionSerializer(many=True)


class AnalyticsFilterSerializer(serializers.Serializer[Any]):
    specialist_id = serializers.IntegerField(min_value=1, required=False)
    service_id = serializers.UUIDField(required=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["from"] = serializers.DateField()
        self.fields["to"] = serializers.DateField()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        date_from = attrs["from"]
        date_to = attrs["to"]
        if date_from > date_to:
            raise serializers.ValidationError(
                {"to": ["Кінець періоду не може бути раніше за початок."]}
            )
        if date_to - date_from > timedelta(days=365):
            raise serializers.ValidationError(
                {"to": ["Аналітичний період не може перевищувати 366 днів."]}
            )
        return attrs


class AnalyticsOptionSerializer(serializers.Serializer[Any]):
    id = serializers.CharField()
    name = serializers.CharField()
    is_active = serializers.BooleanField()


class AnalyticsPeriodSerializer(serializers.Serializer[Any]):
    date_from = serializers.DateField(source="from")
    date_to = serializers.DateField(source="to")
    timezone = serializers.CharField()
    bucket = serializers.ChoiceField(choices=("day", "week", "month"))


class AnalyticsAppliedFiltersSerializer(serializers.Serializer[Any]):
    specialist = AnalyticsOptionSerializer(allow_null=True)
    service = AnalyticsOptionSerializer(allow_null=True)


class AnalyticsKpiSerializer(serializers.Serializer[Any]):
    completed_visits = serializers.IntegerField()
    revenue_minor = serializers.IntegerField()
    payment_count = serializers.IntegerField()
    average_check_minor = serializers.IntegerField()
    returning_patient_rate_bps = serializers.IntegerField()
    returning_patients = serializers.IntegerField()
    served_patients = serializers.IntegerField()
    new_patients = serializers.IntegerField()
    canceled_appointments = serializers.IntegerField()
    no_show_appointments = serializers.IntegerField()
    average_return_interval_days = serializers.IntegerField(allow_null=True)


class AnalyticsTrendPointSerializer(serializers.Serializer[Any]):
    date_from = serializers.DateField(source="from")
    date_to = serializers.DateField(source="to")
    visits = serializers.IntegerField()
    revenue_minor = serializers.IntegerField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["label"] = serializers.CharField()


class AnalyticsOutcomeSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    count = serializers.IntegerField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["label"] = serializers.CharField()


class AnalyticsSpecialistPerformanceSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    name = serializers.CharField()
    is_active = serializers.BooleanField()
    completed_visits = serializers.IntegerField()
    scheduled_minutes = serializers.IntegerField()
    available_minutes = serializers.IntegerField()
    utilization_bps = serializers.IntegerField()
    revenue_minor = serializers.IntegerField()


class AnalyticsServiceRankingSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    visit_count = serializers.IntegerField()
    quantity = serializers.IntegerField()
    billed_total_minor = serializers.IntegerField()


class AnalyticsResponseSerializer(serializers.Serializer[Any]):
    period = AnalyticsPeriodSerializer()
    filters = AnalyticsAppliedFiltersSerializer()
    available_specialists = AnalyticsOptionSerializer(many=True)
    available_services = AnalyticsOptionSerializer(many=True)
    kpis = AnalyticsKpiSerializer()
    trend = AnalyticsTrendPointSerializer(many=True)
    appointment_outcomes = AnalyticsOutcomeSerializer(many=True)
    specialist_performance = AnalyticsSpecialistPerformanceSerializer(many=True)
    service_ranking = AnalyticsServiceRankingSerializer(many=True)
