import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(int(default))).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


def env_optional_bool(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def env_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return int(value)


def env_secret(name: str, default: str | None = None) -> str:
    direct_value = os.getenv(name)
    file_name = os.getenv(f"{name}_FILE")
    if direct_value is not None and file_name:
        raise ImproperlyConfigured(f"Set only one of {name} or {name}_FILE.")
    if file_name:
        try:
            value = Path(file_name).read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as exc:
            raise ImproperlyConfigured(f"Cannot read {name}_FILE.") from exc
        if not value:
            raise ImproperlyConfigured(f"{name}_FILE must not be empty.")
        return value
    if direct_value is not None:
        if not direct_value:
            raise ImproperlyConfigured(f"{name} must not be empty.")
        return direct_value
    if default is None:
        raise ImproperlyConfigured(f"{name} or {name}_FILE must be set.")
    return default


SECRET_KEY = env_secret("DJANGO_SECRET_KEY", "dev-only-change-before-production")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
if not DEBUG and SECRET_KEY == "dev-only-change-before-production":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set outside local development.")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8088")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "apps.accounts",
    "apps.audit",
    "apps.clinic",
    "apps.patients",
    "apps.work_items",
    "apps.booking_requests",
    "apps.scheduling",
    "apps.inventory",
    "apps.visits",
    "apps.discounts",
    "apps.billing",
    "apps.global_search",
    "apps.notifications",
    "apps.operations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.RequestIdMiddleware",
    "config.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.middleware.SessionExpiryMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "podoria"),
        "USER": os.getenv("POSTGRES_USER", "podoria"),
        "PASSWORD": env_secret("POSTGRES_PASSWORD", "podoria_dev_password"),
        "HOST": os.getenv("POSTGRES_HOST", "postgres"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "uk"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
TEMPORARY_PASSWORD_TTL_HOURS = int(os.getenv("TEMPORARY_PASSWORD_TTL_HOURS", "24"))

SESSION_COOKIE_NAME = "podoria_sessionid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
COOKIE_SECURE_OVERRIDE = env_optional_bool("DJANGO_COOKIE_SECURE")
SESSION_COOKIE_SECURE = not DEBUG if COOKIE_SECURE_OVERRIDE is None else COOKIE_SECURE_OVERRIDE
SESSION_IDLE_TIMEOUT_SECONDS = env_int("SESSION_IDLE_TIMEOUT_SECONDS", 30 * 60)
SESSION_ABSOLUTE_TIMEOUT_SECONDS = env_int("SESSION_ABSOLUTE_TIMEOUT_SECONDS", 12 * 60 * 60)
SESSION_COOKIE_AGE = SESSION_ABSOLUTE_TIMEOUT_SECONDS
CSRF_COOKIE_NAME = "podoria_csrftoken"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_FAILURE_VIEW = "config.api.csrf.csrf_failure"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SSL_REDIRECT_OVERRIDE = env_optional_bool("DJANGO_SECURE_SSL_REDIRECT")
SECURE_SSL_REDIRECT = not DEBUG if SSL_REDIRECT_OVERRIDE is None else SSL_REDIRECT_OVERRIDE
SECURE_REDIRECT_EXEMPT = [r"^health/"]
HSTS_SECONDS_OVERRIDE = env_optional_int("DJANGO_SECURE_HSTS_SECONDS")
SECURE_HSTS_SECONDS = (
    (0 if DEBUG else 31_536_000) if HSTS_SECONDS_OVERRIDE is None else HSTS_SECONDS_OVERRIDE
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

CONTENT_SECURITY_POLICY = os.getenv(
    "CONTENT_SECURITY_POLICY",
    "default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; "
    "object-src 'none'; script-src 'self'; style-src 'self'; font-src 'self' data:; "
    "connect-src 'self'; img-src 'self' data: blob:",
)
PERMISSIONS_POLICY = os.getenv(
    "PERMISSIONS_POLICY",
    "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
)

LOGIN_RATE_LIMIT_WINDOW_SECONDS = env_int("LOGIN_RATE_LIMIT_WINDOW_SECONDS", 15 * 60)
LOGIN_RATE_LIMIT_EMAIL_ATTEMPTS = env_int("LOGIN_RATE_LIMIT_EMAIL_ATTEMPTS", 5)
LOGIN_RATE_LIMIT_IP_ATTEMPTS = env_int("LOGIN_RATE_LIMIT_IP_ATTEMPTS", 30)
LOGIN_RATE_LIMIT_TRUSTED_PROXY_COUNT = env_int("LOGIN_RATE_LIMIT_TRUSTED_PROXY_COUNT", 1)
BOOKING_REQUEST_API_RATE_LIMIT_ATTEMPTS = env_int(
    "BOOKING_REQUEST_API_RATE_LIMIT_ATTEMPTS",
    60,
)
BOOKING_REQUEST_API_RATE_LIMIT_WINDOW_SECONDS = env_int(
    "BOOKING_REQUEST_API_RATE_LIMIT_WINDOW_SECONDS",
    60,
)
BOOKING_REQUEST_API_INVALID_ATTEMPTS = env_int(
    "BOOKING_REQUEST_API_INVALID_ATTEMPTS",
    30,
)
BOOKING_REQUEST_API_INVALID_WINDOW_SECONDS = env_int(
    "BOOKING_REQUEST_API_INVALID_WINDOW_SECONDS",
    15 * 60,
)
BOOKING_REQUEST_API_TRUSTED_PROXY_COUNT = env_int(
    "BOOKING_REQUEST_API_TRUSTED_PROXY_COUNT",
    LOGIN_RATE_LIMIT_TRUSTED_PROXY_COUNT,
)
TELEGRAM_BOT_TOKEN = env_secret("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = env_secret("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "podo_crm_pod_bot")
TELEGRAM_API_BASE_URL = os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org")
TELEGRAM_REQUEST_TIMEOUT_SECONDS = env_int("TELEGRAM_REQUEST_TIMEOUT_SECONDS", 5)
TELEGRAM_LINK_INTENT_TTL_SECONDS = env_int("TELEGRAM_LINK_INTENT_TTL_SECONDS", 10 * 60)
TELEGRAM_DELIVERY_RETRY_BASE_SECONDS = env_int("TELEGRAM_DELIVERY_RETRY_BASE_SECONDS", 60)
TELEGRAM_DELIVERY_RETRY_MAX_SECONDS = env_int("TELEGRAM_DELIVERY_RETRY_MAX_SECONDS", 60 * 60)
TELEGRAM_DELIVERY_MAX_ATTEMPTS = env_int("TELEGRAM_DELIVERY_MAX_ATTEMPTS", 8)
CRM_PUBLIC_URL = os.getenv("CRM_PUBLIC_URL", "http://localhost:8088")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHE_BACKEND = os.getenv(
    "DJANGO_CACHE_BACKEND",
    "django.core.cache.backends.redis.RedisCache",
)
CACHES = {
    "default": {
        "BACKEND": CACHE_BACKEND,
        "LOCATION": REDIS_URL if CACHE_BACKEND.endswith("RedisCache") else "podoria-security",
        "TIMEOUT": LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    }
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.SessionAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.api.exceptions.api_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Podoria CRM API",
    "DESCRIPTION": "Versioned API contract for Podoria CRM.",
    "VERSION": "1.0.0",
    "OAS_VERSION": "3.0.3",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "ENUM_NAME_OVERRIDES": {
        "CashLedgerEntryKindEnum": "apps.billing.models.CashLedgerEntryKind",
        "CashMovementTypeEnum": "apps.billing.serializers.CASH_MOVEMENT_TYPES",
        "CashShiftStatusEnum": "apps.billing.models.CashShiftStatus",
        "InventoryOperationKindEnum": "apps.inventory.models.InventoryOperationKind",
        "BookingRequestStatusEnum": "apps.booking_requests.models.BookingRequestStatus",
        "PaymentMethodEnum": "apps.billing.models.PaymentMethod",
        "PostedFinanceStatusEnum": "apps.billing.serializers.POSTED_FINANCE_STATUSES",
        "ReceivableStatusEnum": "apps.billing.models.ReceivableStatus",
        "DetectedConditionEnum": "apps.visits.models.DetectedCondition",
        "VisitPhotoKindEnum": "apps.visits.models.VisitPhotoKind",
        "VisitPhotoPreviewStatusEnum": "apps.visits.models.VisitPhotoPreviewStatus",
        "VisitStatusEnum": "apps.visits.models.VisitStatus",
        "WorkItemKindEnum": "apps.work_items.models.WorkItemKind",
        "GlobalSearchGroupTypeEnum": ("apps.global_search.serializers.GLOBAL_SEARCH_GROUP_TYPES"),
        "GlobalSearchItemTypeEnum": ("apps.global_search.serializers.GLOBAL_SEARCH_ITEM_TYPES"),
    },
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "config.api.schema.require_work_item_update_version",
        "config.api.schema.close_finance_mutation_request_schemas",
    ],
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TIMEZONE = TIME_ZONE

MINIO_HEALTH_URL = os.getenv(
    "MINIO_HEALTH_URL",
    "http://minio:9000/minio/health/ready",
)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = env_secret("MINIO_ACCESS_KEY", "podoria_minio")
MINIO_SECRET_KEY = env_secret("MINIO_SECRET_KEY", "podoria_minio_dev_password")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "podoria-private")
CLINIC_LOGO_MAX_BYTES = 5 * 1024 * 1024
CLINIC_LOGO_MAX_DIMENSION = env_int("CLINIC_LOGO_MAX_DIMENSION", 6000)
VISIT_PHOTO_MAX_BYTES = 10 * 1024 * 1024
VISIT_PHOTO_MAX_PER_KIND = 10
VISIT_PHOTO_INTENT_TTL_SECONDS = 60 * 60
VISIT_PHOTO_INTENT_CLEANUP_SECONDS = 24 * 60 * 60
VISIT_PHOTO_SIGNED_URL_SECONDS = 5 * 60
CELERY_BEAT_SCHEDULE = {
    "cleanup-expired-visit-photo-intents": {
        "task": "apps.visits.tasks.cleanup_expired_visit_photo_intents",
        "schedule": 60 * 60,
    },
    "dispatch-due-notification-reminders": {
        "task": "apps.notifications.tasks.dispatch_due_notification_reminders",
        "schedule": 60,
    },
    "dispatch-notification-telegram-deliveries": {
        "task": "apps.notifications.tasks.dispatch_notification_telegram_deliveries",
        "schedule": 60,
    },
    "dispatch-telegram-booking-request-deliveries": {
        "task": "apps.booking_requests.tasks.dispatch_telegram_booking_request_deliveries",
        "schedule": 60,
    },
    "dispatch-telegram-work-item-deliveries": {
        "task": "apps.booking_requests.tasks.dispatch_telegram_work_item_deliveries",
        "schedule": 60,
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "config.logging.JsonFormatter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "podoria": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
