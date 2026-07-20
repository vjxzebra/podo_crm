from io import BytesIO
from urllib.parse import urlparse

from django.conf import settings
from minio import Minio


def _client() -> Minio:
    parsed = urlparse(settings.MINIO_ENDPOINT)
    endpoint = parsed.netloc or parsed.path
    return Minio(
        endpoint,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=parsed.scheme == "https",
    )


def put_private_object(*, object_key: str, content: bytes, content_type: str) -> None:
    _client().put_object(
        settings.MINIO_BUCKET_NAME,
        object_key,
        BytesIO(content),
        length=len(content),
        content_type=content_type,
    )


def get_private_object(*, object_key: str) -> bytes:
    response = _client().get_object(settings.MINIO_BUCKET_NAME, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_private_object(*, object_key: str) -> None:
    if object_key:
        _client().remove_object(settings.MINIO_BUCKET_NAME, object_key)
