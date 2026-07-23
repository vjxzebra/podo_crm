from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User, UserRole


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
    notification_unread_count = serializers.IntegerField(min_value=0)
    must_change_password = serializers.BooleanField()
    temporary_password_expires_at = serializers.DateTimeField(allow_null=True)
    temporary_password_expired = serializers.BooleanField()


class PasswordPairSerializer(serializers.Serializer):
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password_confirmation = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        if attrs["new_password"] != attrs["new_password_confirmation"]:
            raise serializers.ValidationError(
                {"new_password_confirmation": ["Паролі не збігаються."]}
            )
        user = self.context.get("user")
        try:
            validate_password(
                attrs["new_password"],
                user=user if isinstance(user, User) else None,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": exc.messages}) from exc
        return attrs


class ChangePasswordRequestSerializer(PasswordPairSerializer):
    current_password = serializers.CharField(trim_whitespace=False, write_only=True)


class PasswordResetRequestCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetRequestAcceptedSerializer(serializers.Serializer):
    message = serializers.CharField()


class PasswordResetRequestUserSerializer(SessionUserSerializer):
    pass


class PasswordResetRequestItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    requested_at = serializers.DateTimeField()
    user = PasswordResetRequestUserSerializer()


class PasswordResetRequestListSerializer(serializers.Serializer):
    requests = PasswordResetRequestItemSerializer(many=True)


class TemporaryPasswordRequestSerializer(serializers.Serializer):
    temporary_password = serializers.CharField(trim_whitespace=False, write_only=True)
    temporary_password_confirmation = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        if attrs["temporary_password"] != attrs["temporary_password_confirmation"]:
            raise serializers.ValidationError(
                {"temporary_password_confirmation": ["Паролі не збігаються."]}
            )
        user = self.context.get("user")
        try:
            validate_password(
                attrs["temporary_password"],
                user=user if isinstance(user, User) else None,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"temporary_password": exc.messages}) from exc
        return attrs


class TemporaryPasswordResultSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    must_change_password = serializers.BooleanField()
    temporary_password_expires_at = serializers.DateTimeField()
