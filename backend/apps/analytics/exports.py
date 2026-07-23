import csv
from collections.abc import Mapping, Sequence
from datetime import date
from io import StringIO
from typing import Any, cast

from config.api.csv import spreadsheet_safe_text

ANALYTICS_EXPORT_ROW_LIMIT = 5000
ANALYTICS_EXPORT_COLUMNS = (
    "row_type",
    "period_from",
    "period_to",
    "timezone",
    "bucket",
    "filter_specialist_id",
    "filter_specialist_name",
    "filter_service_id",
    "filter_service_name",
    "sequence",
    "dimension_from",
    "dimension_to",
    "dimension_id",
    "dimension_code",
    "dimension_name",
    "is_active",
    "completed_visits",
    "revenue_minor",
    "payment_count",
    "average_check_minor",
    "returning_patient_rate_bps",
    "returning_patients",
    "served_patients",
    "new_patients",
    "canceled_appointments",
    "no_show_appointments",
    "average_return_interval_days",
    "visits",
    "appointment_count",
    "scheduled_minutes",
    "available_minutes",
    "utilization_bps",
    "quantity",
    "billed_total_minor",
)


def _iso_date(value: object) -> str:
    return value.isoformat() if isinstance(value, date) else str(value)


def _rows(result: Mapping[str, Any]) -> list[dict[str, object]]:
    period = cast(Mapping[str, Any], result["period"])
    filters = cast(Mapping[str, Any], result["filters"])
    specialist = cast(Mapping[str, Any] | None, filters["specialist"])
    service = cast(Mapping[str, Any] | None, filters["service"])
    common: dict[str, object] = {
        "period_from": _iso_date(period["from"]),
        "period_to": _iso_date(period["to"]),
        "timezone": spreadsheet_safe_text(period["timezone"]),
        "bucket": spreadsheet_safe_text(period["bucket"]),
        "filter_specialist_id": "" if specialist is None else specialist["id"],
        "filter_specialist_name": (
            "" if specialist is None else spreadsheet_safe_text(specialist["name"])
        ),
        "filter_service_id": "" if service is None else service["id"],
        "filter_service_name": ("" if service is None else spreadsheet_safe_text(service["name"])),
    }
    kpis = cast(Mapping[str, Any], result["kpis"])
    rows: list[dict[str, object]] = [
        {
            **common,
            "row_type": "REPORT_SUMMARY",
            "completed_visits": kpis["completed_visits"],
            "revenue_minor": kpis["revenue_minor"],
            "payment_count": kpis["payment_count"],
            "average_check_minor": kpis["average_check_minor"],
            "returning_patient_rate_bps": kpis["returning_patient_rate_bps"],
            "returning_patients": kpis["returning_patients"],
            "served_patients": kpis["served_patients"],
            "new_patients": kpis["new_patients"],
            "canceled_appointments": kpis["canceled_appointments"],
            "no_show_appointments": kpis["no_show_appointments"],
            "average_return_interval_days": (
                ""
                if kpis["average_return_interval_days"] is None
                else kpis["average_return_interval_days"]
            ),
        }
    ]
    for sequence, item in enumerate(cast(Sequence[Mapping[str, Any]], result["trend"]), start=1):
        rows.append(
            {
                **common,
                "row_type": "TREND",
                "sequence": sequence,
                "dimension_from": _iso_date(item["from"]),
                "dimension_to": _iso_date(item["to"]),
                "dimension_name": spreadsheet_safe_text(item["label"]),
                "visits": item["visits"],
                "revenue_minor": item["revenue_minor"],
            }
        )
    for sequence, item in enumerate(
        cast(Sequence[Mapping[str, Any]], result["appointment_outcomes"]), start=1
    ):
        rows.append(
            {
                **common,
                "row_type": "APPOINTMENT_OUTCOME",
                "sequence": sequence,
                "dimension_code": spreadsheet_safe_text(item["code"]),
                "dimension_name": spreadsheet_safe_text(item["label"]),
                "appointment_count": item["count"],
            }
        )
    for sequence, item in enumerate(
        cast(Sequence[Mapping[str, Any]], result["specialist_performance"]), start=1
    ):
        rows.append(
            {
                **common,
                "row_type": "SPECIALIST_PERFORMANCE",
                "sequence": sequence,
                "dimension_id": item["id"],
                "dimension_name": spreadsheet_safe_text(item["name"]),
                "is_active": "true" if item["is_active"] else "false",
                "completed_visits": item["completed_visits"],
                "revenue_minor": item["revenue_minor"],
                "scheduled_minutes": item["scheduled_minutes"],
                "available_minutes": item["available_minutes"],
                "utilization_bps": item["utilization_bps"],
            }
        )
    for sequence, item in enumerate(
        cast(Sequence[Mapping[str, Any]], result["service_ranking"]), start=1
    ):
        rows.append(
            {
                **common,
                "row_type": "SERVICE_RANKING",
                "sequence": sequence,
                "dimension_id": item["id"],
                "dimension_code": spreadsheet_safe_text(item["code"]),
                "dimension_name": spreadsheet_safe_text(item["name"]),
                "visits": item["visit_count"],
                "quantity": item["quantity"],
                "billed_total_minor": item["billed_total_minor"],
            }
        )
    return rows


def analytics_export_row_count(result: Mapping[str, Any]) -> int:
    return (
        1
        + len(cast(Sequence[object], result["trend"]))
        + len(cast(Sequence[object], result["appointment_outcomes"]))
        + len(cast(Sequence[object], result["specialist_performance"]))
        + len(cast(Sequence[object], result["service_ranking"]))
    )


def render_analytics_csv(result: Mapping[str, Any]) -> bytes:
    output = StringIO(newline="")
    csv_writer = csv.DictWriter(
        output,
        fieldnames=ANALYTICS_EXPORT_COLUMNS,
        dialect="excel",
        lineterminator="\r\n",
    )
    csv_writer.writeheader()
    csv_writer.writerows(_rows(result))
    return output.getvalue().encode("utf-8-sig")
