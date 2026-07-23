from django.urls import path

from apps.accounts.team_views import (
    TeamUserDeactivateView,
    TeamUserDetailView,
    TeamUserListCreateView,
)
from apps.accounts.views import (
    ChangePasswordView,
    FirstLoginPasswordView,
    LoginView,
    LogoutView,
    PasswordResetRequestView,
    SessionView,
    TemporaryPasswordView,
)

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path(
        "auth/first-login-password",
        FirstLoginPasswordView.as_view(),
        name="auth-first-login-password",
    ),
    path("auth/change-password", ChangePasswordView.as_view(), name="auth-change-password"),
    path(
        "password-reset-requests",
        PasswordResetRequestView.as_view(),
        name="password-reset-requests",
    ),
    path(
        "users/<int:user_id>/temporary-password",
        TemporaryPasswordView.as_view(),
        name="user-temporary-password",
    ),
    path("users", TeamUserListCreateView.as_view(), name="team-user-list-create"),
    path("users/<int:user_id>", TeamUserDetailView.as_view(), name="team-user-detail"),
    path(
        "users/<int:user_id>/deactivate",
        TeamUserDeactivateView.as_view(),
        name="team-user-deactivate",
    ),
    path("session", SessionView.as_view(), name="session"),
]
