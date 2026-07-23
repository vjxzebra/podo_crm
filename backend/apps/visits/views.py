from uuid import UUID

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.visits.finish_services import (
    finish_result_read_model,
    finish_visit,
)
from apps.visits.photo_services import (
    create_photo_upload_intent,
    delete_visit_photo,
    finalize_visit_photo,
    get_visit_photo,
    intent_read_model,
    photo_read_model,
    resolve_signed_photo_content,
)
from apps.visits.recommendation_services import (
    create_visit_recommendation,
    get_visit_recommendation,
    recommendation_read_model,
    update_visit_recommendation,
)
from apps.visits.serializers import (
    StartVisitSerializer,
    VisitDraftUpdateSerializer,
    VisitFinishResponseSerializer,
    VisitFinishSerializer,
    VisitMaterialOptionListSerializer,
    VisitMaterialOptionQuerySerializer,
    VisitPhotoContentQuerySerializer,
    VisitPhotoFinalizeSerializer,
    VisitPhotoIntentCreateSerializer,
    VisitPhotoSerializer,
    VisitPhotoUploadIntentSerializer,
    VisitRecommendationCreateSerializer,
    VisitRecommendationSerializer,
    VisitRecommendationUpdateSerializer,
    VisitResponseSerializer,
)
from apps.visits.services import (
    get_visit,
    list_visit_material_options,
    save_visit_draft,
    start_visit,
    visit_read_model,
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


def _idempotency_key(request: Request) -> str:
    value = request.headers.get("Idempotency-Key", "").strip()
    if not value:
        raise ApiProblem(
            code="idempotency_key_required",
            message="Для завершення прийому потрібен Idempotency-Key.",
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


FINISH_IDEMPOTENCY_PARAMETER = OpenApiParameter(
    name="Idempotency-Key",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=True,
    description="Stable per-submit key. Same payload replays the original completion result.",
)


class StartVisitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="visit_start",
        summary="Start one visit for an arrived appointment",
        request=StartVisitSerializer,
        responses={
            status.HTTP_200_OK: VisitResponseSerializer,
            status.HTTP_201_CREATED: VisitResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def post(self, request: Request, appointment_id: UUID) -> Response:
        serializer = StartVisitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visit, created = start_visit(
            actor=_actor(request),
            appointment_id=appointment_id,
            requested_version=serializer.validated_data["version"],
            correlation_id=get_request_id(request),
        )
        return Response(
            VisitResponseSerializer(visit_read_model(visit)).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class VisitDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="visit_retrieve",
        summary="Read a role-scoped clinical visit workspace",
        responses={
            status.HTTP_200_OK: VisitResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def get(self, request: Request, visit_id: UUID) -> Response:
        visit = get_visit(actor=_actor(request), visit_id=visit_id)
        return Response(VisitResponseSerializer(visit_read_model(visit)).data)

    @extend_schema(
        operation_id="visit_draft_update",
        summary="Save a versioned visit draft without posting side effects",
        request=VisitDraftUpdateSerializer,
        responses={
            status.HTTP_200_OK: VisitResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def put(self, request: Request, visit_id: UUID) -> Response:
        serializer = VisitDraftUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visit = save_visit_draft(
            actor=_actor(request),
            visit_id=visit_id,
            requested_version=serializer.validated_data["version"],
            data=serializer.validated_data,
            correlation_id=get_request_id(request),
        )
        return Response(VisitResponseSerializer(visit_read_model(visit)).data)


class VisitFinishView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="visit_finish",
        summary="Atomically finish a visit, post stock and create one receivable",
        request=VisitFinishSerializer,
        parameters=[FINISH_IDEMPOTENCY_PARAMETER],
        responses={
            status.HTTP_200_OK: VisitFinishResponseSerializer,
            status.HTTP_201_CREATED: VisitFinishResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def post(self, request: Request, visit_id: UUID) -> Response:
        serializer = VisitFinishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = _actor(request)
        result, replayed = finish_visit(
            actor=actor,
            visit_id=visit_id,
            idempotency_key=_idempotency_key(request),
            data=dict(serializer.validated_data),
            correlation_id=get_request_id(request),
        )
        return Response(
            VisitFinishResponseSerializer(
                finish_result_read_model(actor=actor, result=result, replayed=replayed)
            ).data,
            status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        )


class VisitMaterialOptionListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="visit_material_option_list",
        summary="Search role-scoped usable material lots for a visit draft",
        parameters=[VisitMaterialOptionQuerySerializer],
        responses={
            status.HTTP_200_OK: VisitMaterialOptionListSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def get(self, request: Request, visit_id: UUID) -> Response:
        serializer = VisitMaterialOptionQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        materials = list_visit_material_options(
            actor=_actor(request),
            visit_id=visit_id,
            search=serializer.validated_data.get("search", "").strip(),
        )
        return Response(VisitMaterialOptionListSerializer({"materials": materials}).data)


class VisitPhotoUploadIntentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="visit_photo_upload_intent_create",
        summary="Create a short-lived private visit-photo upload intent",
        request=VisitPhotoIntentCreateSerializer,
        responses={
            status.HTTP_201_CREATED: VisitPhotoUploadIntentSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def post(self, request: Request, visit_id: UUID) -> Response:
        serializer = VisitPhotoIntentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        intent = create_photo_upload_intent(
            actor=_actor(request),
            visit_id=visit_id,
            kind=serializer.validated_data["kind"],
        )
        return Response(
            VisitPhotoUploadIntentSerializer(intent_read_model(intent)).data,
            status=status.HTTP_201_CREATED,
        )


class VisitPhotoFinalizeView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @extend_schema(
        operation_id="visit_photo_finalize",
        summary="Validate, canonicalize and finalize one private visit photo",
        request=VisitPhotoFinalizeSerializer,
        responses={
            status.HTTP_200_OK: VisitPhotoSerializer,
            status.HTTP_201_CREATED: VisitPhotoSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
            status.HTTP_503_SERVICE_UNAVAILABLE: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def post(self, request: Request, visit_id: UUID) -> Response:
        serializer = VisitPhotoFinalizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo, created = finalize_visit_photo(
            actor=_actor(request),
            visit_id=visit_id,
            intent_id=serializer.validated_data["intent_id"],
            upload=serializer.validated_data["photo"],
            correlation_id=get_request_id(request),
        )
        photo = get_visit_photo(actor=_actor(request), visit_id=visit_id, photo_id=photo.pk)
        return Response(
            VisitPhotoSerializer(photo_read_model(photo)).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class VisitPhotoDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="visit_photo_retrieve",
        summary="Authorize and return metadata with five-minute signed photo URLs",
        responses={
            status.HTTP_200_OK: VisitPhotoSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def get(self, request: Request, visit_id: UUID, photo_id: UUID) -> Response:
        photo = get_visit_photo(
            actor=_actor(request),
            visit_id=visit_id,
            photo_id=photo_id,
        )
        return Response(VisitPhotoSerializer(photo_read_model(photo)).data)

    @extend_schema(
        operation_id="visit_photo_delete",
        summary="Delete one photo while its visit remains a draft",
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def delete(self, request: Request, visit_id: UUID, photo_id: UUID) -> Response:
        delete_visit_photo(
            actor=_actor(request),
            visit_id=visit_id,
            photo_id=photo_id,
            correlation_id=get_request_id(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class VisitPhotoContentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="visit_photo_content_retrieve",
        summary="Read private photo bytes through an expiring signed URL",
        parameters=[VisitPhotoContentQuerySerializer],
        responses={
            (status.HTTP_200_OK, "image/jpeg"): bytes,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
            status.HTTP_503_SERVICE_UNAVAILABLE: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def get(self, request: Request) -> HttpResponse:
        serializer = VisitPhotoContentQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        content, content_type = resolve_signed_photo_content(
            actor=_actor(request),
            token=serializer.validated_data["token"],
        )
        response = HttpResponse(content, content_type=content_type)
        response["Cache-Control"] = "private, no-store"
        response["Content-Disposition"] = 'inline; filename="visit-photo"'
        response["X-Content-Type-Options"] = "nosniff"
        return response


class VisitRecommendationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="visit_recommendation_create",
        summary="Add an authored recommendation to a completed visit",
        request=VisitRecommendationCreateSerializer,
        responses={
            status.HTTP_201_CREATED: VisitRecommendationSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def post(self, request: Request, visit_id: UUID) -> Response:
        serializer = VisitRecommendationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recommendation = create_visit_recommendation(
            actor=_actor(request),
            visit_id=visit_id,
            text=serializer.validated_data["text"],
            correlation_id=get_request_id(request),
        )
        return Response(
            VisitRecommendationSerializer(recommendation_read_model(recommendation)).data,
            status=status.HTTP_201_CREATED,
        )


class VisitRecommendationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="visit_recommendation_retrieve",
        summary="Refresh one recommendation after medical object-scope authorization",
        responses={
            status.HTTP_200_OK: VisitRecommendationSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def get(
        self,
        request: Request,
        visit_id: UUID,
        recommendation_id: UUID,
    ) -> Response:
        recommendation = get_visit_recommendation(
            actor=_actor(request),
            visit_id=visit_id,
            recommendation_id=recommendation_id,
        )
        return Response(
            VisitRecommendationSerializer(recommendation_read_model(recommendation)).data
        )

    @extend_schema(
        operation_id="visit_recommendation_update",
        summary="Update an authored recommendation with optimistic versioning",
        request=VisitRecommendationUpdateSerializer,
        responses={
            status.HTTP_200_OK: VisitRecommendationSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["visits"],
    )
    def patch(
        self,
        request: Request,
        visit_id: UUID,
        recommendation_id: UUID,
    ) -> Response:
        serializer = VisitRecommendationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recommendation = update_visit_recommendation(
            actor=_actor(request),
            visit_id=visit_id,
            recommendation_id=recommendation_id,
            requested_version=serializer.validated_data["version"],
            text=serializer.validated_data["text"],
            correlation_id=get_request_id(request),
        )
        return Response(
            VisitRecommendationSerializer(recommendation_read_model(recommendation)).data
        )
