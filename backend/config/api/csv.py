from collections.abc import Mapping
from typing import Any

from rest_framework.renderers import BaseRenderer, JSONRenderer

SPREADSHEET_FORMULA_PREFIXES = frozenset(("=", "+", "-", "@"))


def spreadsheet_safe_text(value: object) -> str:
    text = "" if value is None else str(value).replace("\x00", "")
    if text.lstrip()[:1] in SPREADSHEET_FORMULA_PREFIXES:
        return f"'{text}"
    return text


class SafeCsvRenderer(BaseRenderer):
    media_type = "text/csv"
    format = "csv"
    charset = None
    render_style = "binary"

    def render(
        self,
        data: Any,
        accepted_media_type: str | None = None,
        renderer_context: Mapping[str, Any] | None = None,
    ) -> bytes:
        return JSONRenderer().render(data, accepted_media_type, renderer_context)
