from typing import Any

from rest_framework import serializers

from apps.discounts.models import Discount, LoyaltyPolicy


class DiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discount
        fields = (
            "id",
            "name",
            "percent",
            "is_active",
            "version",
            "created_at",
            "updated_at",
        )


class DiscountListSerializer(serializers.Serializer):
    discounts = DiscountSerializer(many=True)


class DiscountCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, allow_blank=False)
    percent = serializers.IntegerField(min_value=1, max_value=99)
    is_active = serializers.BooleanField(default=True)

    def validate_name(self, value: str) -> str:
        return value.strip()


class DiscountUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, allow_blank=False, required=False)
    percent = serializers.IntegerField(min_value=1, max_value=99, required=False)
    is_active = serializers.BooleanField(required=False)
    version = serializers.IntegerField(min_value=1)

    def validate_name(self, value: str) -> str:
        return value.strip()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if len(attrs) == 1:
            raise serializers.ValidationError("Укажіть хоча б одну зміну.")
        return attrs


class LoyaltyPolicySerializer(serializers.ModelSerializer):
    discount = DiscountSerializer(allow_null=True)

    class Meta:
        model = LoyaltyPolicy
        fields = (
            "key",
            "is_active",
            "every_n",
            "discount",
            "version",
            "started_at",
            "updated_at",
        )


class LoyaltyPolicyUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False)
    every_n = serializers.IntegerField(min_value=1, max_value=10000, required=False)
    discount_id = serializers.UUIDField(required=False, allow_null=True)
    version = serializers.IntegerField(min_value=1)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if len(attrs) == 1:
            raise serializers.ValidationError("Укажіть хоча б одну зміну.")
        return attrs
