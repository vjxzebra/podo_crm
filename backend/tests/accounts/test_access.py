import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.accounts.access import ROLE_ROUTE_IDS, AccessScope, has_scope
from apps.accounts.models import User, UserRole
from apps.accounts.permissions import HasFinanceAccess, HasInventoryAccess, HasMedicalAccess


class MedicalProbeView(APIView):
    permission_classes = [HasMedicalAccess]

    def get(self, request):
        return None


class FinanceProbeView(APIView):
    permission_classes = [HasFinanceAccess]

    def get(self, request):
        return None


class InventoryProbeView(APIView):
    permission_classes = [HasInventoryAccess]

    def get(self, request):
        return None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "view_type", "expected"),
    [
        (UserRole.PODOLOGIST, MedicalProbeView, True),
        (UserRole.PODOLOGIST, FinanceProbeView, False),
        (UserRole.PODOLOGIST, InventoryProbeView, False),
        (UserRole.RECEPTION, MedicalProbeView, False),
        (UserRole.RECEPTION, FinanceProbeView, True),
        (UserRole.RECEPTION, InventoryProbeView, False),
        (UserRole.ADMIN, MedicalProbeView, True),
        (UserRole.ADMIN, FinanceProbeView, True),
        (UserRole.ADMIN, InventoryProbeView, True),
    ],
)
def test_central_permissions_enforce_role_matrix(role, view_type, expected):
    user = User.objects.create_user(email=f"{role}@example.test", role=role)
    request = APIRequestFactory().get("/")
    force_authenticate(request, user=user)
    wrapped_request = view_type().initialize_request(request)

    assert (
        view_type.permission_classes[0]().has_permission(
            wrapped_request,
            view_type(),
        )
        is expected
    )


@pytest.mark.django_db
def test_inactive_user_has_no_scope():
    user = User.objects.create_user(
        email="inactive@example.test",
        role=UserRole.ADMIN,
        is_active=False,
    )

    assert has_scope(user, AccessScope.SETTINGS) is False


def test_route_matrix_keeps_medical_and_financial_modules_separated():
    assert "finance" not in ROLE_ROUTE_IDS[UserRole.PODOLOGIST]
    assert "inventory" not in ROLE_ROUTE_IDS[UserRole.PODOLOGIST]
    assert "inventory" not in ROLE_ROUTE_IDS[UserRole.RECEPTION]
    assert "settings" not in ROLE_ROUTE_IDS[UserRole.RECEPTION]
    assert "audit" in ROLE_ROUTE_IDS[UserRole.ADMIN]
    assert "audit" not in ROLE_ROUTE_IDS[UserRole.RECEPTION]
    assert "audit" not in ROLE_ROUTE_IDS[UserRole.PODOLOGIST]
    assert set(ROLE_ROUTE_IDS[UserRole.PODOLOGIST]) < set(ROLE_ROUTE_IDS[UserRole.ADMIN])
    assert set(ROLE_ROUTE_IDS[UserRole.RECEPTION]) < set(ROLE_ROUTE_IDS[UserRole.ADMIN])


@pytest.mark.django_db
def test_email_is_case_insensitively_unique_in_database():
    User.objects.create_user(email="Admin@Example.Test", role=UserRole.ADMIN)

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(email="ADMIN@EXAMPLE.TEST", role=UserRole.ADMIN)
