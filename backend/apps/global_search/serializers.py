import re
import unicodedata
from typing import Any

from rest_framework import serializers

GLOBAL_SEARCH_GROUP_TYPES = (
    "patients",
    "appointments",
    "payments",
    "materials",
)
GLOBAL_SEARCH_ITEM_TYPES = (
    "patient",
    "appointment",
    "payment",
    "material",
)


def normalize_search_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip().casefold()


class NormalizedSearchQueryField(serializers.CharField):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("min_length", 2)
        kwargs.setdefault("max_length", 100)
        kwargs.setdefault("trim_whitespace", False)
        super().__init__(**kwargs)

    def to_internal_value(self, data: Any) -> str:
        if isinstance(data, str):
            data = normalize_search_query(data)
        return super().to_internal_value(data)


class GlobalSearchFilterSerializer(serializers.Serializer[Any]):
    q = NormalizedSearchQueryField()
    types = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=160,
        trim_whitespace=False,
    )

    def validate_types(self, value: str) -> tuple[str, ...]:
        raw_values = value.split(",")
        requested: list[str] = []
        invalid: list[str] = []
        for raw_value in raw_values:
            normalized = raw_value.strip().casefold()
            if not normalized or normalized not in GLOBAL_SEARCH_GROUP_TYPES:
                invalid.append(raw_value.strip() or "(порожній тип)")
                continue
            if normalized not in requested:
                requested.append(normalized)
        if invalid:
            raise serializers.ValidationError("Невідомі типи пошуку: " + ", ".join(invalid) + ".")
        return tuple(requested)


class GlobalSearchItemSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=GLOBAL_SEARCH_ITEM_TYPES)
    id = serializers.UUIDField()
    title = serializers.CharField()
    subtitle = serializers.CharField()
    meta = serializers.CharField()
    deep_link = serializers.CharField()


class GlobalSearchGroupSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=GLOBAL_SEARCH_GROUP_TYPES)
    has_more = serializers.BooleanField()
    items = GlobalSearchItemSerializer(many=True)


class GlobalSearchResponseSerializer(serializers.Serializer[Any]):
    query = serializers.CharField()
    groups = GlobalSearchGroupSerializer(many=True)
    returned_count = serializers.IntegerField(min_value=0)
