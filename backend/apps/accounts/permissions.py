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


class HasPatientAccess(HasScope):
    required_scope = AccessScope.PATIENT_SAFE


class HasWorkItemAccess(HasScope):
    required_scope = AccessScope.WORK_ITEMS


class HasBookingRequestAccess(HasScope):
    required_scope = AccessScope.BOOKING_REQUESTS


class HasFinanceAccess(HasScope):
    required_scope = AccessScope.FINANCE


class HasCashShiftAccess(HasScope):
    required_scope = AccessScope.CASH_SHIFT


class HasInventoryAccess(HasScope):
    required_scope = AccessScope.INVENTORY


class HasAuditAccess(HasScope):
    required_scope = AccessScope.AUDIT


class HasAnalyticsAccess(HasScope):
    required_scope = AccessScope.ANALYTICS


class HasTeamAccess(HasScope):
    required_scope = AccessScope.TEAM


class IsAdmin(HasScope):
    required_scope = AccessScope.SETTINGS
