from django.urls import path

from apps.accounts.views import LoginView, LogoutView, SessionView

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("session", SessionView.as_view(), name="session"),
]
