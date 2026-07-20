from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import route_ids_for
from apps.accounts.models import User
from apps.accounts.serializers import LoginRequestSerializer, SessionSerializer
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
        "route_ids": list(route_ids_for(user)),
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
