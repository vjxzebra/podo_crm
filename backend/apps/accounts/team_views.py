from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import HasTeamAccess
from apps.accounts.team_serializers import (
    TeamUserCreateSerializer,
    TeamUserFilterSerializer,
    TeamUserListSerializer,
    TeamUserSerializer,
    TeamUserUpdateSerializer,
)
from apps.accounts.team_services import (
    create_team_user,
    deactivate_team_user,
    update_team_user,
)
from config.api.exceptions import ApiProblem
from config.api.serializers import ErrorEnvelopeSerializer
from config.middleware import get_request_id


def _authenticated_user(request: Request) -> User:
    if not isinstance(request.user, User):
        raise ApiProblem(
            code="authentication_required",
            message="Потрібна автентифікація.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return request.user


class TeamUserListCreateView(APIView):
    permission_classes = [HasTeamAccess]

    @extend_schema(
        operation_id="team_user_list",
        summary="List and filter employees for an administrator",
        parameters=[TeamUserFilterSerializer],
        responses={
            status.HTTP_200_OK: TeamUserListSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["team"],
    )
    def get(self, request: Request) -> Response:
        filters = TeamUserFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        query = filters.validated_data
        users = User.objects.all()
        if search := query.get("search", "").strip():
            users = users.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )
        if query.get("status") == "active":
            users = users.filter(is_active=True)
        elif query.get("status") == "inactive":
            users = users.filter(is_active=False)
        if role := query.get("role"):
            users = users.filter(role=role)
        users = users.order_by("-is_active", "first_name", "last_name", "pk")
        return Response({"users": TeamUserSerializer(users, many=True).data})

    @extend_schema(
        operation_id="team_user_create",
        summary="Create an employee with initial password policy",
        request=TeamUserCreateSerializer,
        responses={
            status.HTTP_201_CREATED: TeamUserSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["team"],
    )
    def post(self, request: Request) -> Response:
        serializer = TeamUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = create_team_user(
                actor=_authenticated_user(request),
                correlation_id=get_request_id(request),
                data=serializer.validated_data,
            )
        except IntegrityError as exc:
            raise ApiProblem(
                code="email_already_exists",
                message="Працівник із таким email уже існує.",
                status_code=status.HTTP_409_CONFLICT,
                fields={"email": ["Укажіть інший робочий email."]},
            ) from exc
        return Response(TeamUserSerializer(user).data, status=status.HTTP_201_CREATED)


class TeamUserDetailView(APIView):
    permission_classes = [HasTeamAccess]

    @extend_schema(
        operation_id="team_user_retrieve",
        summary="Return one employee profile",
        responses={
            status.HTTP_200_OK: TeamUserSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["team"],
    )
    def get(self, request: Request, user_id: int) -> Response:
        user = get_object_or_404(User, pk=user_id)
        return Response(TeamUserSerializer(user).data)

    @extend_schema(
        operation_id="team_user_update",
        summary="Update contacts, role or active state with last-admin protection",
        request=TeamUserUpdateSerializer,
        responses={
            status.HTTP_200_OK: TeamUserSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["team"],
    )
    def patch(self, request: Request, user_id: int) -> Response:
        target = get_object_or_404(User, pk=user_id)
        serializer = TeamUserUpdateSerializer(
            data=request.data,
            context={"target": target},
        )
        serializer.is_valid(raise_exception=True)
        try:
            updated = update_team_user(
                actor=_authenticated_user(request),
                target_id=user_id,
                correlation_id=get_request_id(request),
                changes=serializer.validated_data,
            )
        except IntegrityError as exc:
            raise ApiProblem(
                code="email_already_exists",
                message="Працівник із таким email уже існує.",
                status_code=status.HTTP_409_CONFLICT,
                fields={"email": ["Укажіть інший робочий email."]},
            ) from exc
        return Response(TeamUserSerializer(updated).data)


class TeamUserDeactivateView(APIView):
    permission_classes = [HasTeamAccess]

    @extend_schema(
        operation_id="team_user_deactivate",
        summary="Deactivate an employee and revoke their sessions",
        request=None,
        responses={
            status.HTTP_200_OK: TeamUserSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
        },
        tags=["team"],
    )
    def post(self, request: Request, user_id: int) -> Response:
        get_object_or_404(User, pk=user_id)
        user = deactivate_team_user(
            actor=_authenticated_user(request),
            target_id=user_id,
            correlation_id=get_request_id(request),
        )
        return Response(TeamUserSerializer(user).data)
