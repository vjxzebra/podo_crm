from urllib.parse import parse_qs, urlparse
from uuid import UUID

from django.db import IntegrityError
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import HasInventoryAccess
from apps.inventory.models import (
    InventoryOperation,
    Material,
    MaterialLot,
    StockMovement,
    Stocktake,
)
from apps.inventory.serializers import (
    InventoryOperationSerializer,
    ManualWriteoffCreateSerializer,
    MaterialCreateSerializer,
    MaterialFilterSerializer,
    MaterialListSerializer,
    MaterialLotListSerializer,
    MaterialLotSerializer,
    MaterialSerializer,
    MaterialUpdateSerializer,
    MovementFilterSerializer,
    MovementJournalItemSerializer,
    MovementJournalResponseSerializer,
    ReceiptCreateSerializer,
    StocktakeCreateSerializer,
    StocktakePreviewSerializer,
    StocktakeSerializer,
)
from apps.inventory.services import (
    create_material,
    create_stocktake,
    post_manual_writeoff,
    post_receipt,
    post_stocktake,
    update_material,
)
from config.api.exceptions import ApiProblem
from config.api.serializers import ErrorEnvelopeSerializer
from config.middleware import get_request_id


def _actor(request: Request) -> User:
    if not isinstance(request.user, User):
        raise ApiProblem(
            code="authentication_required",
            message="Потрібна автентифікація.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return request.user


def _sku_conflict() -> ApiProblem:
    return ApiProblem(
        code="material_sku_already_exists",
        message="Матеріал із таким артикулом уже існує.",
        status_code=status.HTTP_409_CONFLICT,
        fields={"sku": ["Укажіть інший унікальний артикул."]},
    )


def _materials_with_lots() -> QuerySet[Material]:
    return Material.objects.prefetch_related("lots")


def _idempotency_key(request: Request) -> str:
    value = request.headers.get("Idempotency-Key", "").strip()
    if not value:
        raise ApiProblem(
            code="idempotency_key_required",
            message="Для проведення складської операції потрібен Idempotency-Key.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"idempotency_key": ["Створіть стабільний ключ для цього submit."]},
        )
    if len(value) > 128:
        raise ApiProblem(
            code="idempotency_key_invalid",
            message="Idempotency-Key перевищує дозволену довжину.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"idempotency_key": ["Максимальна довжина — 128 символів."]},
        )
    return value


IDEMPOTENCY_PARAMETER = OpenApiParameter(
    name="Idempotency-Key",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=True,
    description=(
        "Stable per-submit key. A retry with the same payload returns the original operation."
    ),
)


class MovementCursorPagination(CursorPagination):
    page_size = 40
    ordering = ("-created_at", "-id")


def _cursor_from_link(link: str | None) -> str | None:
    if not link:
        return None
    return parse_qs(urlparse(link).query).get("cursor", [None])[0]


def _stocktake_queryset() -> QuerySet[Stocktake]:
    return Stocktake.objects.select_related(
        "created_by", "posted_by", "operation"
    ).prefetch_related("lines__lot__material", "operation__movements__lot__material")


class MaterialListCreateView(APIView):
    permission_classes = [HasInventoryAccess]

    @extend_schema(
        operation_id="inventory_material_list",
        summary="Search and filter the administrator material catalog with stock projections",
        parameters=[MaterialFilterSerializer],
        responses={
            status.HTTP_200_OK: MaterialListSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def get(self, request: Request) -> Response:
        filters = MaterialFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        query = filters.validated_data
        materials = _materials_with_lots().all()
        if search := query.get("search", "").strip():
            materials = materials.filter(Q(sku__icontains=search) | Q(name__icontains=search))
        if category := query.get("category", "").strip():
            materials = materials.filter(category__iexact=category)
        if query.get("status") == "active":
            materials = materials.filter(is_active=True)
        elif query.get("status") == "inactive":
            materials = materials.filter(is_active=False)
        material_list = list(materials)
        if query.get("stock_status") not in (None, "all"):
            material_list = [
                item for item in material_list if item.stock_status == query["stock_status"]
            ]
        return Response({"materials": MaterialSerializer(material_list, many=True).data})

    @extend_schema(
        operation_id="inventory_material_create",
        summary="Create an administrator material catalog record",
        request=MaterialCreateSerializer,
        responses={
            status.HTTP_201_CREATED: MaterialSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def post(self, request: Request) -> Response:
        serializer = MaterialCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            material = create_material(
                actor=_actor(request),
                correlation_id=get_request_id(request),
                data=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise _sku_conflict() from exc
        return Response(MaterialSerializer(material).data, status=status.HTTP_201_CREATED)


class MaterialDetailView(APIView):
    permission_classes = [HasInventoryAccess]

    @extend_schema(
        operation_id="inventory_material_retrieve",
        summary="Return administrator material details and current stock projections",
        responses={
            status.HTTP_200_OK: MaterialSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def get(self, request: Request, material_id: UUID) -> Response:
        material = get_object_or_404(_materials_with_lots(), pk=material_id)
        return Response(MaterialSerializer(material).data)

    @extend_schema(
        operation_id="inventory_material_update",
        summary="Edit or deactivate a material while protecting unit and historical stock identity",
        request=MaterialUpdateSerializer,
        responses={
            status.HTTP_200_OK: MaterialSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def patch(self, request: Request, material_id: UUID) -> Response:
        get_object_or_404(Material, pk=material_id)
        serializer = MaterialUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            material = update_material(
                actor=_actor(request),
                material_id=material_id,
                correlation_id=get_request_id(request),
                changes=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise _sku_conflict() from exc
        material = get_object_or_404(_materials_with_lots(), pk=material.pk)
        return Response(MaterialSerializer(material).data)


class MaterialLotListView(APIView):
    permission_classes = [HasInventoryAccess]

    @extend_schema(
        operation_id="inventory_material_lot_list",
        summary="List material lots with expiry, usability and FEFO projections",
        responses={
            status.HTTP_200_OK: MaterialLotListSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def get(self, request: Request, material_id: UUID) -> Response:
        get_object_or_404(Material, pk=material_id)
        lots = list(MaterialLot.objects.filter(material_id=material_id))
        usable = sorted(
            (item for item in lots if item.is_usable),
            key=lambda item: (item.expires_on is None, item.expires_on, item.received_on, item.pk),
        )
        fefo_ranks = {item.pk: index for index, item in enumerate(usable, start=1)}
        lots.sort(
            key=lambda item: (
                not item.is_usable,
                item.expires_on is None,
                item.expires_on,
                item.received_on,
                item.pk,
            )
        )
        return Response(
            {
                "lots": MaterialLotSerializer(
                    lots,
                    many=True,
                    context={"fefo_ranks": fefo_ranks},
                ).data
            }
        )


class ReceiptCreateView(APIView):
    permission_classes = [HasInventoryAccess]

    @extend_schema(
        operation_id="inventory_receipt_create",
        summary="Post a multi-line material receipt atomically",
        parameters=[IDEMPOTENCY_PARAMETER],
        request=ReceiptCreateSerializer,
        responses={
            status.HTTP_200_OK: InventoryOperationSerializer,
            status.HTTP_201_CREATED: InventoryOperationSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def post(self, request: Request) -> Response:
        serializer = ReceiptCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        operation, replayed = post_receipt(
            actor=_actor(request),
            correlation_id=get_request_id(request),
            idempotency_key=_idempotency_key(request),
            data=dict(serializer.validated_data),
        )
        return Response(
            InventoryOperationSerializer(operation, context={"replayed": replayed}).data,
            status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        )


class ManualWriteoffCreateView(APIView):
    permission_classes = [HasInventoryAccess]

    @extend_schema(
        operation_id="inventory_manual_writeoff_create",
        summary="Post a locked manual stock write-off without allowing a negative balance",
        parameters=[IDEMPOTENCY_PARAMETER],
        request=ManualWriteoffCreateSerializer,
        responses={
            status.HTTP_200_OK: InventoryOperationSerializer,
            status.HTTP_201_CREATED: InventoryOperationSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def post(self, request: Request) -> Response:
        serializer = ManualWriteoffCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        operation, replayed = post_manual_writeoff(
            actor=_actor(request),
            correlation_id=get_request_id(request),
            idempotency_key=_idempotency_key(request),
            data=dict(serializer.validated_data),
        )
        return Response(
            InventoryOperationSerializer(operation, context={"replayed": replayed}).data,
            status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        )


class StocktakePreviewView(APIView):
    permission_classes = [HasInventoryAccess]

    @extend_schema(
        operation_id="inventory_stocktake_preview",
        summary="Return the current per-lot balances for a physical stocktake",
        responses={
            status.HTTP_200_OK: StocktakePreviewSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def get(self, request: Request) -> Response:
        lots = MaterialLot.objects.select_related("material").order_by(
            "material__name", "material__sku", "lot_number", "pk"
        )
        preview = StocktakePreviewSerializer({"lots": lots})
        return Response(preview.data)


class StocktakeListCreateView(APIView):
    permission_classes = [HasInventoryAccess]

    @extend_schema(
        operation_id="inventory_stocktake_create",
        summary="Freeze an immutable physical-count draft against the current lot balances",
        parameters=[IDEMPOTENCY_PARAMETER],
        request=StocktakeCreateSerializer,
        responses={
            status.HTTP_200_OK: StocktakeSerializer,
            status.HTTP_201_CREATED: StocktakeSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def post(self, request: Request) -> Response:
        serializer = StocktakeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stocktake, replayed = create_stocktake(
            actor=_actor(request),
            correlation_id=get_request_id(request),
            idempotency_key=_idempotency_key(request),
            data=dict(serializer.validated_data),
        )
        return Response(
            StocktakeSerializer(stocktake, context={"replayed": replayed}).data,
            status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        )


class StocktakeDetailView(APIView):
    permission_classes = [HasInventoryAccess]

    @extend_schema(
        operation_id="inventory_stocktake_retrieve",
        summary="Return the immutable physical-count draft or posted stocktake",
        responses={
            status.HTTP_200_OK: StocktakeSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def get(self, request: Request, stocktake_id: UUID) -> Response:
        stocktake = get_object_or_404(_stocktake_queryset(), pk=stocktake_id)
        return Response(StocktakeSerializer(stocktake).data)


class StocktakePostView(APIView):
    permission_classes = [HasInventoryAccess]

    @extend_schema(
        operation_id="inventory_stocktake_post",
        summary="Post a stocktake atomically as append-only lot adjustments",
        parameters=[IDEMPOTENCY_PARAMETER],
        request=None,
        responses={
            status.HTTP_200_OK: StocktakeSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def post(self, request: Request, stocktake_id: UUID) -> Response:
        get_object_or_404(Stocktake, pk=stocktake_id)
        stocktake, replayed = post_stocktake(
            actor=_actor(request),
            stocktake_id=stocktake_id,
            correlation_id=get_request_id(request),
            idempotency_key=_idempotency_key(request),
        )
        return Response(
            StocktakeSerializer(stocktake, context={"replayed": replayed}).data,
            status=status.HTTP_200_OK,
        )


class MovementListView(APIView):
    permission_classes = [HasInventoryAccess]

    @extend_schema(
        operation_id="inventory_movement_list",
        summary="Search and cursor-page the append-only stock movement journal",
        parameters=[MovementFilterSerializer],
        responses={
            status.HTTP_200_OK: MovementJournalResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def get(self, request: Request) -> Response:
        filters = MovementFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        query = filters.validated_data
        movements = StockMovement.objects.select_related(
            "operation__created_by", "lot__material"
        ).all()
        if search := query.get("search", "").strip():
            movements = movements.filter(
                Q(operation__public_number__icontains=search)
                | Q(operation__reason__icontains=search)
                | Q(operation__comment__icontains=search)
                | Q(lot__lot_number__icontains=search)
                | Q(lot__material__sku__icontains=search)
                | Q(lot__material__name__icontains=search)
            )
        if query.get("kind") not in (None, "all"):
            movements = movements.filter(operation__kind=query["kind"])
        if material_id := query.get("material_id"):
            movements = movements.filter(lot__material_id=material_id)
        if actor := query.get("actor", "").strip():
            movements = movements.filter(
                Q(operation__created_by__email__icontains=actor)
                | Q(operation__created_by__first_name__icontains=actor)
                | Q(operation__created_by__last_name__icontains=actor)
            )
        if date_from := query.get("date_from"):
            movements = movements.filter(operation__posted_at__date__gte=date_from)
        if date_to := query.get("date_to"):
            movements = movements.filter(operation__posted_at__date__lte=date_to)

        paginator = MovementCursorPagination()
        page = paginator.paginate_queryset(movements, request, view=self)
        return Response(
            {
                "movements": MovementJournalItemSerializer(page, many=True).data,
                "next_cursor": _cursor_from_link(paginator.get_next_link()),
            }
        )


class InventoryOperationDetailView(APIView):
    permission_classes = [HasInventoryAccess]

    @extend_schema(
        operation_id="inventory_operation_retrieve",
        summary="Return a read-only inventory operation with all append-only movements",
        responses={
            status.HTTP_200_OK: InventoryOperationSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["inventory"],
    )
    def get(self, request: Request, operation_id: UUID) -> Response:
        operation = get_object_or_404(
            InventoryOperation.objects.select_related("created_by").prefetch_related(
                "movements__lot__material"
            ),
            pk=operation_id,
        )
        return Response(InventoryOperationSerializer(operation).data)
