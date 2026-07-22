from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Case, IntegerField, Prefetch, Q, QuerySet, Value, When
from django.db.models.functions import Greatest

from apps.accounts.access import AccessScope, has_scope
from apps.accounts.models import User
from apps.inventory.models import Material, MaterialLot


def materials_visible_to(actor: User) -> QuerySet[Material]:
    if not has_scope(actor, AccessScope.INVENTORY):
        return Material.objects.none()
    return Material.objects.prefetch_related("lots")


def materials_for_global_search(actor: User, search: str) -> QuerySet[Material]:
    term = search.strip()
    return (
        materials_visible_to(actor)
        .prefetch_related(None)
        .only(
            "id",
            "sku",
            "name",
            "category",
            "unit",
            "minimum_quantity",
            "is_active",
        )
        .prefetch_related(
            Prefetch(
                "lots",
                queryset=MaterialLot.objects.only(
                    "id",
                    "material_id",
                    "current_quantity",
                    "expires_on",
                ).order_by("expires_on", "id"),
            )
        )
        .filter(Q(sku__icontains=term) | Q(name__icontains=term))
        .alias(
            global_search_rank=Case(
                When(sku__iexact=term, then=Value(0)),
                When(sku__istartswith=term, then=Value(1)),
                When(name__istartswith=term, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            ),
            global_search_similarity=Greatest(
                TrigramSimilarity("sku", term),
                TrigramSimilarity("name", term),
            ),
        )
        .order_by("global_search_rank", "-global_search_similarity", "name", "sku", "id")
    )
