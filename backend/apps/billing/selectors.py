from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import (
    Case,
    CharField,
    DateTimeField,
    Exists,
    Func,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Concat, Greatest

from apps.accounts.access import AccessScope, has_scope
from apps.accounts.models import User
from apps.billing.models import CashLedgerEntry, Payment, Receivable
from apps.patients.normalization import phone_digits
from apps.visits.models import Visit, VisitServiceLine


def _payments_with_context() -> QuerySet[Payment]:
    return Payment.objects.select_related(
        "ledger_entry__cash_shift",
        "ledger_entry__created_by",
        "refund_record__ledger_entry__cash_shift",
        "refund_record__ledger_entry__created_by",
    )


def _payments_for_global_search() -> QuerySet[Payment]:
    return Payment.objects.select_related("ledger_entry").only(
        "id",
        "receivable_id",
        "patient_name_snapshot",
        "ledger_entry__id",
        "ledger_entry__public_number",
        "ledger_entry__payment_method",
    )


def _payment_receivables_scope(actor: User) -> QuerySet[Receivable]:
    if not has_scope(actor, AccessScope.FINANCE):
        return Receivable.objects.none()
    return Receivable.objects.all()


def payment_receivables_visible_to(actor: User) -> QuerySet[Receivable]:
    return (
        _payment_receivables_scope(actor)
        .select_related(
            "visit__patient",
            "visit__specialist",
        )
        .prefetch_related(
            "visit__service_lines",
            Prefetch("payment_records", queryset=_payments_with_context()),
        )
        .defer(
            "visit__complaints",
            "visit__objective_examination",
            "visit__detected_conditions",
            "visit__podologist_notes",
        )
        .annotate(
            operation_occurred_at=Coalesce(
                "payment_records__ledger_entry__posted_at",
                "visit__completed_at",
                "created_at",
                output_field=DateTimeField(),
            ),
            patient_search_name=Concat(
                "visit__patient__first_name",
                Value(" "),
                "visit__patient__last_name",
                output_field=CharField(),
            ),
        )
    )


def payment_receivables_for_global_search(
    actor: User,
    search: str,
) -> QuerySet[Receivable]:
    from apps.patients.selectors import patients_visible_to, search_patients

    term = search.strip()
    digits = phone_digits(term)
    payment_phone_digits = Func(
        "patient_phone_snapshot",
        Value("[^0-9]"),
        Value(""),
        Value("g"),
        function="REGEXP_REPLACE",
        output_field=CharField(),
    )
    paid_snapshot_matches = (
        Q(patient_name_snapshot__icontains=term)
        | Q(patient_public_number_snapshot__icontains=term)
        | Q(visit_public_number_snapshot__icontains=term)
        | Q(services_search_snapshot__icontains=term)
    )
    if digits:
        paid_snapshot_matches |= Q(global_search_phone_digits__contains=digits)
    matching_paid_receivable_ids = (
        Payment.objects.annotate(global_search_phone_digits=payment_phone_digits)
        .filter(paid_snapshot_matches)
        .order_by()
        .values("receivable_id")
    )
    # Keep this candidate materialized so PostgreSQL can use the ledger trigram index
    # instead of flattening the semi-join into per-payment primary-key lookups.
    matching_ledger_entry_ids = (
        CashLedgerEntry.objects.filter(public_number__icontains=term)
        .order_by()
        .values("pk")
        .distinct()
    )
    matching_ledger_receivable_ids = (
        Payment.objects.filter(ledger_entry_id__in=Subquery(matching_ledger_entry_ids))
        .order_by()
        .values("receivable_id")
    )
    matching_patient_ids = (
        search_patients(
            patients_visible_to(actor).select_related(None),
            term,
        )
        .order_by()
        .values("pk")
    )
    matching_visit_ids = Visit.objects.filter(public_number__icontains=term).order_by().values("pk")
    matching_service_visit_ids = (
        VisitServiceLine.objects.filter(
            Q(service_code__icontains=term) | Q(service_name__icontains=term)
        )
        .order_by()
        .values("visit_id")
    )
    unpaid_receivables = _payment_receivables_scope(actor).filter(payment_records__isnull=True)
    matching_unpaid_patient_receivable_ids = (
        unpaid_receivables.filter(
            visit__patient_id__in=Subquery(matching_patient_ids),
        )
        .order_by()
        .values("pk")
    )
    matching_unpaid_visit_receivable_ids = (
        unpaid_receivables.filter(visit_id__in=Subquery(matching_visit_ids)).order_by().values("pk")
    )
    matching_unpaid_service_receivable_ids = (
        unpaid_receivables.filter(visit_id__in=Subquery(matching_service_visit_ids))
        .order_by()
        .values("pk")
    )
    matches = (
        Q(pk__in=Subquery(matching_paid_receivable_ids))
        | Q(pk__in=Subquery(matching_ledger_receivable_ids))
        | Q(pk__in=Subquery(matching_unpaid_patient_receivable_ids))
        | Q(pk__in=Subquery(matching_unpaid_visit_receivable_ids))
        | Q(pk__in=Subquery(matching_unpaid_service_receivable_ids))
    )
    exact_identifier = (
        Q(payment_records__ledger_entry__public_number__iexact=term)
        | Q(payment_records__patient_public_number_snapshot__iexact=term)
        | Q(payment_records__visit_public_number_snapshot__iexact=term)
        | Q(payment_records__isnull=True, visit__public_number__iexact=term)
        | Q(payment_records__isnull=True, visit__patient__public_number__iexact=term)
    )
    identifier_prefix = (
        Q(payment_records__ledger_entry__public_number__istartswith=term)
        | Q(payment_records__patient_public_number_snapshot__istartswith=term)
        | Q(payment_records__visit_public_number_snapshot__istartswith=term)
        | Q(payment_records__services_search_snapshot__istartswith=term)
        | Q(payment_records__isnull=True, visit__public_number__istartswith=term)
        | Q(payment_records__isnull=True, visit__patient__public_number__istartswith=term)
    )
    name_prefix = (
        Q(payment_records__patient_name_snapshot__istartswith=term)
        | Q(payment_records__isnull=True, visit__patient__first_name__istartswith=term)
        | Q(payment_records__isnull=True, visit__patient__last_name__istartswith=term)
        | Q(payment_records__isnull=True, patient_search_name__istartswith=term)
    )
    if digits:
        exact_identifier |= Q(
            payment_records__isnull=True,
            visit__patient__normalized_phone=digits,
        )
        exact_identifier |= Q(payment_phone_digits=digits)
        identifier_prefix |= Q(
            payment_records__isnull=True,
            visit__patient__normalized_phone__startswith=digits,
        )
        identifier_prefix |= Q(payment_phone_digits__startswith=digits)
    exact_service = VisitServiceLine.objects.filter(
        visit_id=OuterRef("visit_id"),
        service_code__iexact=term,
    )
    prefix_service = VisitServiceLine.objects.filter(
        visit_id=OuterRef("visit_id"),
        service_code__istartswith=term,
    )
    name_prefix_service = VisitServiceLine.objects.filter(
        visit_id=OuterRef("visit_id"),
        service_name__istartswith=term,
    )
    return (
        _payment_receivables_scope(actor)
        .select_related("visit__patient")
        .only(
            "id",
            "amount_minor",
            "status",
            "visit__id",
            "visit__public_number",
            "visit__completed_at",
            "visit__patient__id",
            "visit__patient__first_name",
            "visit__patient__last_name",
        )
        .prefetch_related(Prefetch("payment_records", queryset=_payments_for_global_search()))
        .alias(
            operation_occurred_at=Coalesce(
                "payment_records__ledger_entry__posted_at",
                "visit__completed_at",
                "created_at",
                output_field=DateTimeField(),
            ),
            patient_search_name=Concat(
                "visit__patient__first_name",
                Value(" "),
                "visit__patient__last_name",
                output_field=CharField(),
            ),
            payment_phone_digits=Func(
                "payment_records__patient_phone_snapshot",
                Value("[^0-9]"),
                Value(""),
                Value("g"),
                function="REGEXP_REPLACE",
                output_field=CharField(),
            ),
            has_exact_service=Exists(exact_service),
            has_prefix_service=Exists(prefix_service),
            has_name_prefix_service=Exists(name_prefix_service),
        )
        .filter(matches)
        .alias(
            global_search_rank=Case(
                When(exact_identifier | Q(has_exact_service=True), then=Value(0)),
                When(identifier_prefix | Q(has_prefix_service=True), then=Value(1)),
                When(name_prefix | Q(has_name_prefix_service=True), then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            ),
            global_search_similarity=Greatest(
                TrigramSimilarity("payment_records__ledger_entry__public_number", term),
                TrigramSimilarity("payment_records__patient_name_snapshot", term),
                TrigramSimilarity("payment_records__patient_public_number_snapshot", term),
                TrigramSimilarity("payment_records__visit_public_number_snapshot", term),
                TrigramSimilarity("payment_records__services_search_snapshot", term),
                TrigramSimilarity("visit__patient__first_name", term),
                TrigramSimilarity("visit__patient__last_name", term),
                TrigramSimilarity("visit__patient__normalized_phone", digits or term),
                TrigramSimilarity("visit__public_number", term),
            ),
        )
        .order_by(
            "global_search_rank",
            "-global_search_similarity",
            "-operation_occurred_at",
            "-id",
        )
    )
