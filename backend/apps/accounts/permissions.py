from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.access import AccessScope, has_scope
from apps.accounts.models import User


class HasScope(BasePermission):
    required_scope: AccessScope

    def has_permission(self, request: Request, view: APIView) -> bool:
        return isinstance(request.user, User) and has_scope(request.user, self.required_scope)


class HasMedicalAccess(HasScope):
    required_scope = AccessScope.MEDICAL


class HasFinanceAccess(HasScope):
    required_scope = AccessScope.FINANCE


class HasInventoryAccess(HasScope):
    required_scope = AccessScope.INVENTORY


class IsAdmin(HasScope):
    required_scope = AccessScope.SETTINGS
