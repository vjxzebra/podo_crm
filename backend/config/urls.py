from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from config.api.views import ContractFixtureView
from config.health import liveness, readiness

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/live", liveness, name="health-live"),
    path("health/ready", readiness, name="health-ready"),
    path("api/v1/schema", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.audit.urls")),
    path("api/v1/", include("apps.clinic.urls")),
    path(
        "api/v1/contract/fixture",
        ContractFixtureView.as_view(),
        name="contract-fixture",
    ),
]
