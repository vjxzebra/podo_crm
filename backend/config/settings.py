import os
from pathlib import Path

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


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-before-production")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8088")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.accounts",
    "apps.audit",
    "apps.clinic",
    "apps.patients",
    "apps.work_items",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "podoria_dev_password"),
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
CSRF_COOKIE_NAME = "podoria_csrftoken"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_FAILURE_VIEW = "config.api.csrf.csrf_failure"

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
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "config.api.schema.require_work_item_update_version",
    ],
}

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
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
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "podoria_minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "podoria_minio_dev_password")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "podoria-private")
CLINIC_LOGO_MAX_BYTES = 5 * 1024 * 1024

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
