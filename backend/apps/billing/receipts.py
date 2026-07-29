from __future__ import annotations

import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from django.utils import timezone
from PIL import Image as PillowImage
from PIL import ImageOps
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable

from apps.billing.models import Payment, PaymentMethod
from apps.clinic import storage as clinic_storage
from apps.clinic.models import ClinicProfile

_FONT_REGULAR = "PodoriaReceipt"
_FONT_BOLD = "PodoriaReceipt-Bold"
_PAYMENT_METHOD_LABELS: dict[str, str] = {
    PaymentMethod.CASH: "Готівка",
    PaymentMethod.CARD: "Картка",
    PaymentMethod.TRANSFER: "Переказ",
}


@dataclass(frozen=True)
class ReceiptClinic:
    name: str
    phone: str
    email: str
    address: str
    logo: bytes | None


def _font_candidates() -> list[tuple[Path, Path]]:
    configured = os.environ.get("PODORIA_PDF_FONT_DIR", "").strip()
    directories = [
        Path("/usr/share/fonts/dejavu"),
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("C:/Windows/Fonts"),
    ]
    if configured:
        directories.insert(0, Path(configured))
    candidates: list[tuple[Path, Path]] = []
    for directory in directories:
        if directory.name.lower() == "fonts":
            candidates.append((directory / "arial.ttf", directory / "arialbd.ttf"))
        candidates.append((directory / "DejaVuSans.ttf", directory / "DejaVuSans-Bold.ttf"))
    return candidates


def _register_fonts() -> None:
    if _FONT_REGULAR in pdfmetrics.getRegisteredFontNames():
        return
    for regular, bold in _font_candidates():
        if regular.is_file() and bold.is_file():
            pdfmetrics.registerFont(TTFont(_FONT_REGULAR, str(regular)))
            pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(bold)))
            return
    raise RuntimeError(
        "A Unicode PDF font was not found. Install DejaVu Sans or configure PODORIA_PDF_FONT_DIR."
    )


def _clinic_details() -> ReceiptClinic:
    profile = ClinicProfile.objects.filter(key="clinic").first()
    if profile is None:
        return ReceiptClinic(
            name="Podoria Clinic",
            phone="",
            email="",
            address="",
            logo=None,
        )

    logo: bytes | None = None
    if profile.logo_object_key:
        try:
            logo = clinic_storage.get_private_object(object_key=profile.logo_object_key)
        except Exception:
            # The receipt remains available when optional object storage is degraded.
            logo = None
    return ReceiptClinic(
        name=profile.name,
        phone=profile.phone,
        email=profile.email,
        address=profile.address,
        logo=logo,
    )


def _normalized_logo(content: bytes) -> BytesIO | None:
    try:
        with PillowImage.open(BytesIO(content)) as source:
            normalized = ImageOps.exif_transpose(source).convert("RGBA")
            background = PillowImage.new("RGBA", normalized.size, "white")
            background.alpha_composite(normalized)
            monochrome = ImageOps.grayscale(background.convert("RGB"))
            monochrome.thumbnail((800, 320))
            output = BytesIO()
            monochrome.save(output, format="PNG", optimize=True)
            output.seek(0)
            return output
    except (OSError, ValueError):
        return None


def _money(amount_minor: int) -> str:
    whole, remainder = divmod(int(amount_minor), 100)
    return f"{whole:,}".replace(",", " ") + f",{remainder:02d} грн"


def _local_datetime(value: Any) -> str:
    local = timezone.localtime(value)
    return local.strftime("%d.%m.%Y, %H:%M")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "ReceiptBody",
            parent=base["BodyText"],
            fontName=_FONT_REGULAR,
            fontSize=9,
            leading=13,
            textColor=colors.black,
            spaceAfter=0,
        ),
        "small": ParagraphStyle(
            "ReceiptSmall",
            parent=base["BodyText"],
            fontName=_FONT_REGULAR,
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#333333"),
        ),
        "label": ParagraphStyle(
            "ReceiptLabel",
            parent=base["BodyText"],
            fontName=_FONT_REGULAR,
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#555555"),
            textTransform="uppercase",
        ),
        "value": ParagraphStyle(
            "ReceiptValue",
            parent=base["BodyText"],
            fontName=_FONT_BOLD,
            fontSize=9,
            leading=12,
        ),
        "title": ParagraphStyle(
            "ReceiptTitle",
            parent=base["Title"],
            fontName=_FONT_BOLD,
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=3 * mm,
        ),
        "subtitle": ParagraphStyle(
            "ReceiptSubtitle",
            parent=base["BodyText"],
            fontName=_FONT_BOLD,
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            borderWidth=0.7,
            borderColor=colors.black,
            borderPadding=2 * mm,
            spaceAfter=5 * mm,
        ),
        "section": ParagraphStyle(
            "ReceiptSection",
            parent=base["Heading2"],
            fontName=_FONT_BOLD,
            fontSize=10,
            leading=13,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        ),
        "total": ParagraphStyle(
            "ReceiptTotal",
            parent=base["Heading2"],
            fontName=_FONT_BOLD,
            fontSize=13,
            leading=16,
            alignment=TA_RIGHT,
        ),
        "recommendation": ParagraphStyle(
            "ReceiptRecommendation",
            parent=base["BodyText"],
            fontName=_FONT_REGULAR,
            fontSize=10,
            leading=15,
            spaceAfter=4 * mm,
        ),
    }


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    from xml.sax.saxutils import escape

    normalized = escape(str(text or "—")).replace("\n", "<br/>")
    return Paragraph(normalized, style)


def _clinic_header(
    clinic: ReceiptClinic,
    styles: dict[str, ParagraphStyle],
) -> Flowable:
    contact_lines = [clinic.name]
    contact_lines.extend(
        value for value in (clinic.address, clinic.phone, clinic.email) if value.strip()
    )
    contact = _p("\n".join(contact_lines), styles["body"])

    logo_flowable: Flowable | str = ""
    if clinic.logo is not None:
        logo_source = _normalized_logo(clinic.logo)
        if logo_source is not None:
            logo_flowable = Image(logo_source, width=32 * mm, height=16 * mm, kind="proportional")

    header = Table(
        [[logo_flowable, contact]],
        colWidths=[38 * mm, 134 * mm],
        hAlign="LEFT",
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
            ]
        )
    )
    return header


def _facts_table(
    rows: list[tuple[str, Any]],
    styles: dict[str, ParagraphStyle],
) -> Table:
    cells: list[list[Flowable]] = []
    for index in range(0, len(rows), 2):
        pair = rows[index : index + 2]
        row: list[Flowable] = []
        for label, value in pair:
            row.append(
                Table(
                    [[_p(label, styles["label"])], [_p(value, styles["value"])]],
                    colWidths=[82 * mm],
                    style=[
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 1 * mm),
                        ("BOTTOMPADDING", (0, 1), (-1, 1), 2 * mm),
                    ],
                )
            )
        if len(row) == 1:
            row.append(Spacer(1, 1))
        cells.append(row)

    table = Table(cells, colWidths=[86 * mm, 86 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BDBDBD")),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ]
        )
    )
    return table


def _services_table(payment: Payment, styles: dict[str, ParagraphStyle]) -> LongTable:
    headers: list[Flowable] = [
        _p("№", styles["value"]),
        _p("Процедура", styles["value"]),
        _p("К-сть", styles["value"]),
        _p("Ціна", styles["value"]),
        _p("Сума", styles["value"]),
    ]
    data: list[list[Flowable]] = [headers]
    for index, service in enumerate(payment.services_snapshot, start=1):
        name = str(service.get("name", "Послуга"))
        code = str(service.get("code", "")).strip()
        data.append(
            [
                _p(index, styles["body"]),
                _p(f"{name}\n{code}" if code else name, styles["body"]),
                _p(service.get("quantity", 1), styles["body"]),
                _p(_money(int(service.get("unit_price_minor", 0))), styles["body"]),
                _p(_money(int(service.get("line_total_minor", 0))), styles["value"]),
            ]
        )
    table = LongTable(
        data,
        colWidths=[10 * mm, 86 * mm, 16 * mm, 30 * mm, 30 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6E6E6")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#777777")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
            ]
        )
    )
    return table


def _page_footer(canvas: Any, document: Any) -> None:
    canvas.saveState()
    canvas.setFont(_FONT_REGULAR, 7)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawString(20 * mm, 10 * mm, "Podoria CRM · документ сформовано автоматично")
    canvas.drawRightString(190 * mm, 10 * mm, f"Сторінка {document.page}")
    canvas.restoreState()


def render_payment_receipt_pdf(payment: Payment) -> bytes:
    _register_fonts()
    clinic = _clinic_details()
    styles = _styles()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=19 * mm,
        rightMargin=19 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"Квитанція {payment.ledger_entry.public_number}",
        author=clinic.name,
        subject="Квитанція про оплату та бланк рекомендацій",
    )

    ledger = payment.ledger_entry
    visit = payment.receivable.visit
    recommendations = list(visit.recommendations.all())
    payment_method_label = _PAYMENT_METHOD_LABELS.get(
        ledger.payment_method,
        ledger.payment_method,
    )
    story: list[Flowable] = [
        _clinic_header(clinic, styles),
        HRFlowable(width="100%", thickness=0.8, color=colors.black, spaceAfter=5 * mm),
        _p("КВИТАНЦІЯ ПРО ОПЛАТУ", styles["title"]),
        _p("НЕ Є ФІСКАЛЬНИМ ЧЕКОМ", styles["subtitle"]),
        _facts_table(
            [
                ("Номер операції", ledger.public_number),
                ("Дата і час оплати", _local_datetime(ledger.posted_at)),
                ("Прийом", payment.visit_public_number_snapshot),
                ("Завершено", _local_datetime(payment.visit_completed_at_snapshot)),
                (
                    "Пацієнт",
                    f"{payment.patient_name_snapshot} · {payment.patient_public_number_snapshot}",
                ),
                ("Телефон пацієнта", payment.patient_phone_snapshot),
                ("Спеціаліст", payment.specialist_name_snapshot),
                ("Оплату прийняв(-ла)", payment.employee_name_snapshot),
            ],
            styles,
        ),
        _p("Процедури та вартість", styles["section"]),
        _services_table(payment, styles),
        Spacer(1, 4 * mm),
        Table(
            [
                [
                    _p(
                        f"Спосіб оплати: {payment_method_label}",
                        styles["value"],
                    ),
                    _p(f"РАЗОМ: {_money(ledger.amount_minor)}", styles["total"]),
                ]
            ],
            colWidths=[86 * mm, 86 * mm],
            style=[
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
            ],
        ),
    ]
    if payment.comment:
        story.extend(
            [
                _p("Коментар до оплати", styles["section"]),
                _p(payment.comment, styles["body"]),
            ]
        )
    if hasattr(payment, "refund_record"):
        refund = payment.refund_record
        story.extend(
            [
                Spacer(1, 3 * mm),
                _p(
                    f"ОПЛАТУ ПОВНІСТЮ ПОВЕРНЕНО: {refund.ledger_entry.public_number}, "
                    f"{_local_datetime(refund.ledger_entry.posted_at)}.",
                    styles["subtitle"],
                ),
            ]
        )
    story.extend(
        [
            Spacer(1, 4 * mm),
            _p(
                "Цей документ підтверджує запис про оплату в CRM. "
                "Фіскальний чек, якщо він потрібен для цієї розрахункової операції, "
                "формується окремо через зареєстрований РРО/ПРРО.",
                styles["small"],
            ),
            PageBreak(),
            _clinic_header(clinic, styles),
            HRFlowable(width="100%", thickness=0.8, color=colors.black, spaceAfter=6 * mm),
            _p("БЛАНК РЕКОМЕНДАЦІЙ", styles["title"]),
            _facts_table(
                [
                    (
                        "Пацієнт",
                        f"{payment.patient_name_snapshot} · "
                        f"{payment.patient_public_number_snapshot}",
                    ),
                    ("Прийом", payment.visit_public_number_snapshot),
                    ("Дата відвідування", _local_datetime(payment.visit_completed_at_snapshot)),
                    ("Спеціаліст", payment.specialist_name_snapshot),
                ],
                styles,
            ),
            _p("Рекомендації подолога", styles["section"]),
        ]
    )
    if recommendations:
        for index, recommendation in enumerate(recommendations, start=1):
            prefix = f"{index}. " if len(recommendations) > 1 else ""
            story.append(_p(f"{prefix}{recommendation.text}", styles["recommendation"]))
    else:
        story.append(_p("Рекомендації не внесені.", styles["recommendation"]))
    story.extend(
        [
            Spacer(1, 12 * mm),
            Table(
                [
                    [
                        _p("Підпис спеціаліста", styles["small"]),
                        _p("Підпис пацієнта", styles["small"]),
                    ],
                    ["____________________________", "____________________________"],
                ],
                colWidths=[86 * mm, 86 * mm],
                style=[
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 1), (-1, 1), _FONT_REGULAR),
                    ("FONTSIZE", (0, 1), (-1, 1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
                ],
            ),
            Spacer(1, 5 * mm),
            _p(
                "Рекомендації є частиною документації завершеного відвідування. "
                "У разі погіршення стану зверніться до профільного медичного фахівця.",
                styles["small"],
            ),
        ]
    )

    document.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()
