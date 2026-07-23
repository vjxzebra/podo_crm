from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Case, Exists, IntegerField, OuterRef, Q, QuerySet, Value, When
from django.db.models.functions import Concat, Greatest

from apps.accounts.models import User, UserRole
from apps.patients.models import Patient
from apps.patients.normalization import phone_digits


def patients_visible_to(user: User) -> QuerySet[Patient]:
    patients = Patient.objects.select_related("primary_podologist", "medical_profile")
    if user.role in {UserRole.ADMIN, UserRole.RECEPTION}:
        return patients
    if user.role == UserRole.PODOLOGIST:
        from apps.scheduling.models import Appointment

        own_appointment = Appointment.objects.filter(
            patient_id=OuterRef("pk"),
            specialist=user,
        )
        return patients.alias(has_own_appointment=Exists(own_appointment)).filter(
            Q(primary_podologist=user) | Q(has_own_appointment=True)
        )
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
    )
    name_tokens = term.split()
    if len(name_tokens) > 1:
        token_criteria = Q()
        for token in name_tokens:
            token_criteria &= Q(first_name__icontains=token) | Q(last_name__icontains=token)
        criteria |= token_criteria
    if digits:
        criteria |= Q(normalized_phone__icontains=digits)
    return queryset.filter(criteria)


def patients_for_global_search(user: User, search: str) -> QuerySet[Patient]:
    term = search.strip()
    digits = phone_digits(term)
    exact = Q(public_number__iexact=term)
    identifier_prefix = Q(public_number__istartswith=term)
    name_prefix = Q(first_name__istartswith=term) | Q(last_name__istartswith=term)
    if digits:
        exact |= Q(normalized_phone=digits)
        identifier_prefix |= Q(normalized_phone__startswith=digits)
    return (
        search_patients(patients_visible_to(user).select_related(None), term)
        .only("id", "public_number", "first_name", "last_name", "phone")
        .alias(display_name_search=Concat("first_name", Value(" "), "last_name"))
        .alias(
            global_search_rank=Case(
                When(exact, then=Value(0)),
                When(identifier_prefix, then=Value(1)),
                When(
                    name_prefix | Q(display_name_search__istartswith=term),
                    then=Value(2),
                ),
                default=Value(3),
                output_field=IntegerField(),
            ),
            global_search_similarity=Greatest(
                TrigramSimilarity("first_name", term),
                TrigramSimilarity("last_name", term),
                TrigramSimilarity("public_number", term),
                TrigramSimilarity("normalized_phone", digits or term),
            ),
        )
        .order_by(
            "global_search_rank",
            "-global_search_similarity",
            "last_name",
            "first_name",
            "id",
        )
    )
