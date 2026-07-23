import json
import logging
import re
from datetime import UTC, datetime

REDACTED = "[REDACTED]"
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)((?:password|token|secret|authorization|cookie|sessionid|api[_-]?key)\s*[=:]\s*)([^\s,;]+)"
)
BEARER_VALUE = re.compile(r"(?i)(bearer\s+)([^\s,;]+)")


def redact_log_text(value: str) -> str:
    redacted = BEARER_VALUE.sub(lambda match: f"{match.group(1)}{REDACTED}", value)
    return SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}{REDACTED}", redacted)


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
            "message": redact_log_text(record.getMessage()),
        }

        for field in self.extra_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = redact_log_text(self.formatException(record.exc_info))

        return json.dumps(payload, ensure_ascii=False)
