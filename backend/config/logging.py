import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    extra_fields = (
        "request_id",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "dependency",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in self.extra_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)
