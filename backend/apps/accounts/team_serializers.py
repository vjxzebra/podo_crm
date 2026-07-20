from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User, UserRole


class TeamUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    display_name = serializers.CharField()
    phone = serializers.CharField(allow_blank=True)
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=UserRole.choices)
    is_active = serializers.BooleanField()
    must_change_password = serializers.BooleanField()
    temporary_password_expires_at = serializers.DateTimeField(allow_null=True)
    last_login = serializers.DateTimeField(allow_null=True)


class TeamUserListSerializer(serializers.Serializer):
    users = TeamUserSerializer(many=True)


class TeamUserFilterSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)
    status = serializers.ChoiceField(
        required=False,
        choices=["all", "active", "inactive"],
        default="all",
    )
    role = serializers.ChoiceField(required=False, choices=UserRole.choices)


class TeamUserCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, allow_blank=False)
    last_name = serializers.CharField(max_length=150, allow_blank=False)
    phone = serializers.CharField(max_length=32, allow_blank=True, required=False, default="")
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=UserRole.choices)
    temporary_password = serializers.CharField(trim_whitespace=False, write_only=True)
    temporary_password_confirmation = serializers.CharField(
        trim_whitespace=False,
        write_only=True,
    )
    is_active = serializers.BooleanField(default=True)
    must_change_password = serializers.BooleanField(default=True)

    def validate_email(self, value: str) -> str:
        normalized = User.objects.normalize_login(value)
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("Працівник із таким email уже існує.")
        return normalized

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["temporary_password"] != attrs["temporary_password_confirmation"]:
            raise serializers.ValidationError(
                {"temporary_password_confirmation": ["Паролі не збігаються."]}
            )
        candidate = User(
            email=attrs["email"],
            first_name=attrs["first_name"],
            last_name=attrs["last_name"],
            role=attrs["role"],
        )
        try:
            validate_password(attrs["temporary_password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"temporary_password": exc.messages}) from exc
        return attrs


class TeamUserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, allow_blank=False, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=False, required=False)
    phone = serializers.CharField(max_length=32, allow_blank=True, required=False)
    email = serializers.EmailField(max_length=254, required=False)
    role = serializers.ChoiceField(choices=UserRole.choices, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate_email(self, value: str) -> str:
        normalized = User.objects.normalize_login(value)
        target = self.context.get("target")
        users = User.objects.filter(email__iexact=normalized)
        if isinstance(target, User):
            users = users.exclude(pk=target.pk)
        if users.exists():
            raise serializers.ValidationError("Працівник із таким email уже існує.")
        return normalized

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("Укажіть хоча б одну зміну.")
        return attrs
