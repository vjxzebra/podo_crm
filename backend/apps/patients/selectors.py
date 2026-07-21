from django.db.models import Q, QuerySet, Value
from django.db.models.functions import Concat

from apps.accounts.models import User, UserRole
from apps.patients.models import Patient
from apps.patients.normalization import phone_digits


def patients_visible_to(user: User) -> QuerySet[Patient]:
    patients = Patient.objects.select_related("primary_podologist", "medical_profile")
    if user.role in {UserRole.ADMIN, UserRole.RECEPTION}:
        return patients
    if user.role == UserRole.PODOLOGIST:
        # Scheduling packets will extend this relationship with past/future appointments.
        return patients.filter(primary_podologist=user)
    return patients.none()


def search_patients(queryset: QuerySet[Patient], search: str) -> QuerySet[Patient]:
    term = search.strip()
    if not term:
        return queryset
    digits = phone_digits(term)
    criteria = (
        Q(first_name__icontains=term)
        | Q(last_name__icontains=term)
        | Q(public_number__icontains=term)
        | Q(phone__icontains=term)
        | Q(display_name_search__icontains=term)
    )
    if digits:
        criteria |= Q(normalized_phone__icontains=digits)
    return queryset.annotate(
        display_name_search=Concat("first_name", Value(" "), "last_name")
    ).filter(criteria)
