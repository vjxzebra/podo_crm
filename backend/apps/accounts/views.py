from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import route_ids_for
from apps.accounts.models import PasswordResetRequest, User
from apps.accounts.permissions import IsAdmin
from apps.accounts.serializers import (
    ChangePasswordRequestSerializer,
    LoginRequestSerializer,
    PasswordPairSerializer,
    PasswordResetRequestAcceptedSerializer,
    PasswordResetRequestCreateSerializer,
    PasswordResetRequestItemSerializer,
    PasswordResetRequestListSerializer,
    SessionSerializer,
    TemporaryPasswordRequestSerializer,
    TemporaryPasswordResultSerializer,
)
from apps.accounts.services import change_own_password, set_temporary_password
from config.api.exceptions import ApiProblem
from config.api.serializers import ErrorEnvelopeSerializer


def session_payload(user: User) -> dict[str, object]:
    return {
        "user": {
            "id": user.pk,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
        },
        "route_ids": [] if user.must_change_password else list(route_ids_for(user)),
        "must_change_password": user.must_change_password,
        "temporary_password_expires_at": user.temporary_password_expires_at,
        "temporary_password_expired": user.temporary_password_expired,
    }


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="auth_login",
        summary="Create a server session",
        request=LoginRequestSerializer,
        responses={
            status.HTTP_200_OK: SessionSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["authentication"],
    )
    def post(self, request: Request) -> Response:
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request._request,
            username=serializer.validated_data["email"].strip().lower(),
            password=serializer.validated_data["password"],
        )
        if not isinstance(user, User):
            raise ApiProblem(
                code="invalid_credentials",
                message="Неправильний email або пароль.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        login(request._request, user)
        return Response(session_payload(user))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="auth_logout",
        summary="Destroy the current server session",
        request=None,
        responses={status.HTTP_204_NO_CONTENT: None},
        tags=["authentication"],
    )
    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SessionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="session_retrieve",
        summary="Return the authenticated user and server-authorized routes",
        responses={
            status.HTTP_200_OK: SessionSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
        },
        tags=["authentication"],
    )
    def get(self, request: Request) -> Response:
        if not isinstance(request.user, User):
            raise ApiProblem(
                code="authentication_required",
                message="Потрібна автентифікація.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(session_payload(request.user))


class FirstLoginPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="auth_first_login_password",
        summary="Replace a temporary password before entering the workspace",
        request=PasswordPairSerializer,
        responses={
            status.HTTP_200_OK: SessionSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["authentication"],
    )
    def post(self, request: Request) -> Response:
        if not isinstance(request.user, User):
            raise ApiProblem(
                code="authentication_required",
                message="Потрібна автентифікація.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        if not request.user.must_change_password:
            raise ApiProblem(
                code="password_change_not_required",
                message="Тимчасовий пароль для цієї сесії не використовується.",
                status_code=status.HTTP_409_CONFLICT,
            )
        if request.user.temporary_password_expired:
            raise ApiProblem(
                code="temporary_password_expired",
                message="Строк дії тимчасового пароля минув. Створіть новий запит на відновлення.",
                status_code=status.HTTP_409_CONFLICT,
            )
        serializer = PasswordPairSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        updated_user = change_own_password(
            request._request,
            request.user,
            serializer.validated_data["new_password"],
        )
        return Response(session_payload(updated_user))


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="auth_change_password",
        summary="Change the current user's password and revoke other sessions",
        request=ChangePasswordRequestSerializer,
        responses={
            status.HTTP_200_OK: SessionSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["authentication"],
    )
    def post(self, request: Request) -> Response:
        if not isinstance(request.user, User):
            raise ApiProblem(
                code="authentication_required",
                message="Потрібна автентифікація.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = ChangePasswordRequestSerializer(
            data=request.data,
            context={"user": request.user},
        )
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["current_password"]):
            raise ApiProblem(
                code="invalid_current_password",
                message="Поточний пароль указано неправильно.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={"current_password": ["Перевірте поточний пароль."]},
            )
        updated_user = change_own_password(
            request._request,
            request.user,
            serializer.validated_data["new_password"],
        )
        return Response(session_payload(updated_user))


@method_decorator(csrf_protect, name="dispatch")
class PasswordResetRequestView(APIView):
    def get_permissions(self) -> list:
        if self.request.method == "POST":
            return [AllowAny()]
        return [IsAdmin()]

    @extend_schema(
        operation_id="password_reset_request_create",
        summary="Create an enumeration-safe password reset request",
        request=PasswordResetRequestCreateSerializer,
        responses={
            status.HTTP_202_ACCEPTED: PasswordResetRequestAcceptedSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["password lifecycle"],
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordResetRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = User.objects.normalize_login(serializer.validated_data["email"])
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            PasswordResetRequest.objects.get_or_create(user=user, resolved_at__isnull=True)
        return Response(
            {
                "message": (
                    "Якщо активний обліковий запис із таким email існує, "
                    "запит уже доступний адміністратору."
                )
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        operation_id="password_reset_request_list",
        summary="List pending password reset requests for an administrator",
        responses={
            status.HTTP_200_OK: PasswordResetRequestListSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
        },
        tags=["password lifecycle"],
    )
    def get(self, request: Request) -> Response:
        pending = PasswordResetRequest.objects.filter(
            resolved_at__isnull=True,
            user__is_active=True,
        ).select_related("user")
        items = PasswordResetRequestItemSerializer(pending, many=True).data
        return Response({"requests": items})


class TemporaryPasswordView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        operation_id="user_temporary_password_create",
        summary="Set a temporary password and revoke every user session",
        request=TemporaryPasswordRequestSerializer,
        responses={
            status.HTTP_200_OK: TemporaryPasswordResultSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["password lifecycle"],
    )
    @transaction.atomic
    def post(self, request: Request, user_id: int) -> Response:
        if not isinstance(request.user, User):
            raise ApiProblem(
                code="authentication_required",
                message="Потрібна автентифікація.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        target = get_object_or_404(User, pk=user_id)
        if not target.is_active:
            raise ApiProblem(
                code="inactive_user",
                message="Не можна встановити тимчасовий пароль для неактивного працівника.",
                status_code=status.HTTP_409_CONFLICT,
            )
        serializer = TemporaryPasswordRequestSerializer(
            data=request.data,
            context={"user": target},
        )
        serializer.is_valid(raise_exception=True)
        updated_user = set_temporary_password(
            actor=request.user,
            target=target,
            temporary_password=serializer.validated_data["temporary_password"],
        )
        return Response(
            {
                "user_id": updated_user.pk,
                "must_change_password": updated_user.must_change_password,
                "temporary_password_expires_at": updated_user.temporary_password_expires_at,
            }
        )
