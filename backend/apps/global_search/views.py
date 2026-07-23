from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.global_search.selectors import global_search_read_model
from apps.global_search.serializers import (
    GlobalSearchFilterSerializer,
    GlobalSearchResponseSerializer,
)
from config.api.exceptions import ApiProblem
from config.api.serializers import ErrorEnvelopeSerializer


def _actor(request: Request) -> User:
    if not isinstance(request.user, User):
        raise ApiProblem(
            code="authentication_required",
            message="Потрібна автентифікація.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return request.user


class GlobalSearchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="global_search_list",
        summary="Search role-scoped CRM objects and return canonical deep links",
        parameters=[GlobalSearchFilterSerializer],
        responses={
            status.HTTP_200_OK: GlobalSearchResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["search"],
    )
    def get(self, request: Request) -> Response:
        filters = GlobalSearchFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        payload = global_search_read_model(
            actor=_actor(request),
            query=filters.validated_data["q"],
            requested_types=filters.validated_data.get("types"),
        )
        return Response(GlobalSearchResponseSerializer(payload).data)
