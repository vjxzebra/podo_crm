from rest_framework import serializers

from apps.accounts.models import UserRole


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class SessionUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    display_name = serializers.CharField()
    role = serializers.ChoiceField(choices=UserRole.choices)


class SessionSerializer(serializers.Serializer):
    user = SessionUserSerializer()
    route_ids = serializers.ListField(child=serializers.CharField())
