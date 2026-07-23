import csv
from collections.abc import Sequence
from io import StringIO

from django.utils import timezone

from apps.inventory.models import StockMovement
from config.api.csv import spreadsheet_safe_text

MOVEMENT_EXPORT_ROW_LIMIT = 5000
MOVEMENT_EXPORT_COLUMNS = (
    "posted_at_local",
    "operation_number",
    "operation_kind",
    "material_sku",
    "material_name",
    "lot_number",
    "supplier_id",
    "supplier_name",
    "quantity_delta",
    "unit",
    "balance_after",
    "actor_name",
    "actor_email",
    "reason",
    "comment",
)


def render_movement_csv(movements: Sequence[StockMovement]) -> bytes:
    output = StringIO(newline="")
    csv_writer = csv.writer(output, dialect="excel", lineterminator="\r\n")
    csv_writer.writerow(MOVEMENT_EXPORT_COLUMNS)
    for movement in movements:
        operation = movement.operation
        actor = operation.created_by
        lot = movement.lot
        material = lot.material
        csv_writer.writerow(
            (
                timezone.localtime(operation.posted_at).isoformat(timespec="seconds"),
                spreadsheet_safe_text(operation.public_number),
                spreadsheet_safe_text(operation.kind),
                spreadsheet_safe_text(material.sku),
                spreadsheet_safe_text(material.name),
                spreadsheet_safe_text(lot.lot_number),
                "" if lot.supplier_id is None else str(lot.supplier_id),
                spreadsheet_safe_text(lot.supplier_name),
                format(movement.quantity_delta, "f"),
                spreadsheet_safe_text(material.unit),
                format(movement.balance_after, "f"),
                spreadsheet_safe_text(actor.get_full_name() or actor.email),
                spreadsheet_safe_text(actor.email),
                spreadsheet_safe_text(operation.reason),
                spreadsheet_safe_text(operation.comment),
            )
        )
    return output.getvalue().encode("utf-8-sig")
