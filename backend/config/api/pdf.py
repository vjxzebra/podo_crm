from collections.abc import Mapping
from typing import Any

from rest_framework.renderers import BaseRenderer, JSONRenderer


class SafePdfRenderer(BaseRenderer):
    media_type = "application/pdf"
    format = "pdf"
    charset = None
    render_style = "binary"

    def render(
        self,
        data: Any,
        accepted_media_type: str | None = None,
        renderer_context: Mapping[str, Any] | None = None,
    ) -> bytes:
        # Successful receipt responses are Django HttpResponse instances and
        # bypass DRF rendering. This fallback preserves the API error envelope
        # when content negotiation selected application/pdf before an error.
        return JSONRenderer().render(data, accepted_media_type, renderer_context)
