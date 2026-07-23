from rest_framework import serializers


class ErrorEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    fields = serializers.DictField(  # type: ignore[assignment]
        child=serializers.ListField(child=serializers.CharField())
    )
    correlation_id = serializers.CharField()


class ContractFixtureSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok"])
    message = serializers.CharField()
    correlation_id = serializers.CharField()
