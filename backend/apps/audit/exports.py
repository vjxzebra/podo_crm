import csv
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from io import StringIO
from typing import Any

from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.registry import AuditSection
from config.api.csv import spreadsheet_safe_text

AUDIT_EXPORT_ROW_LIMIT = 5000
AUDIT_EXPORT_COLUMNS = (
    "row_type",
    "filter_search",
    "filter_actor_id",
    "filter_section",
    "filter_date_from",
    "filter_date_to",
    "event_count",
    "accounts_count",
    "team_count",
    "settings_count",
    "patients_count",
    "work_items_count",
    "booking_requests_count",
    "scheduling_count",
    "medical_count",
    "visits_count",
    "billing_count",
    "cash_count",
    "inventory_count",
    "event_id",
    "occurred_at_local",
    "actor_name",
    "actor_role",
    "section",
    "action",
    "object_type",
    "object_label",
    "result",
    "description",
)


def _iso_datetime(value: object) -> str:
    return value.isoformat(timespec="seconds") if isinstance(value, datetime) else ""


def _local_iso(value: datetime) -> str:
    return timezone.localtime(value).isoformat(timespec="seconds")


def _common_filters(filters: Mapping[str, Any]) -> dict[str, object]:
    return {
        "filter_search": spreadsheet_safe_text(str(filters.get("search", "")).strip()),
        "filter_actor_id": filters.get("actor_id", ""),
        "filter_section": spreadsheet_safe_text(filters.get("section", "")),
        "filter_date_from": _iso_datetime(filters.get("date_from")),
        "filter_date_to": _iso_datetime(filters.get("date_to")),
    }


def render_audit_csv(
    events: Sequence[AuditEvent],
    filters: Mapping[str, Any],
) -> bytes:
    resolved_events = list(events)
    section_counts = Counter(event.section for event in resolved_events)
    common = _common_filters(filters)
    rows: list[dict[str, object]] = [
        {
            **common,
            "row_type": "REPORT_SUMMARY",
            "event_count": len(resolved_events),
            **{f"{section.value}_count": section_counts[section.value] for section in AuditSection},
        }
    ]
    rows.extend(
        {
            **common,
            "row_type": "AUDIT_EVENT",
            "event_id": event.id,
            "occurred_at_local": _local_iso(event.occurred_at),
            "actor_name": spreadsheet_safe_text(event.actor_display_name),
            "actor_role": spreadsheet_safe_text(event.actor_role),
            "section": spreadsheet_safe_text(event.section),
            "action": spreadsheet_safe_text(event.action),
            "object_type": spreadsheet_safe_text(event.object_type),
            "object_label": spreadsheet_safe_text(event.object_label),
            "result": spreadsheet_safe_text(event.result),
            "description": spreadsheet_safe_text(event.description),
        }
        for event in resolved_events
    )

    output = StringIO(newline="")
    csv_writer = csv.DictWriter(
        output,
        fieldnames=AUDIT_EXPORT_COLUMNS,
        dialect="excel",
        lineterminator="\r\n",
    )
    csv_writer.writeheader()
    csv_writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")
