#!/opt/ops-venv/bin/python3
"""Minimal MinIO backup/restore operations with strict path handling."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from minio import Minio


def read_secret(path: str) -> str:
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"secret file is empty: {path}")
    return value


def make_client(args: argparse.Namespace) -> Minio:
    endpoint = urlsplit(args.endpoint)
    if endpoint.scheme not in {"http", "https"} or not endpoint.netloc:
        raise ValueError("MinIO endpoint must be an http(s) URL")
    if endpoint.path not in {"", "/"} or endpoint.query or endpoint.fragment:
        raise ValueError("MinIO endpoint must not contain a path, query, or fragment")
    return Minio(
        endpoint.netloc,
        access_key=read_secret(args.access_key_file),
        secret_key=read_secret(args.secret_key_file),
        secure=endpoint.scheme == "https",
    )


def safe_object_target(root: Path, object_name: str) -> Path:
    object_path = PurePosixPath(object_name)
    if object_path.is_absolute() or not object_path.parts or ".." in object_path.parts:
        raise ValueError(f"unsafe object key rejected: {object_name!r}")
    target = root.joinpath(*object_path.parts).resolve()
    target.relative_to(root.resolve())
    return target


def download(args: argparse.Namespace) -> dict[str, int | str]:
    client = make_client(args)
    if not client.bucket_exists(args.bucket):
        raise ValueError(f"MinIO bucket does not exist: {args.bucket}")
    destination = Path(args.destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    object_count = 0
    object_bytes = 0
    for item in client.list_objects(args.bucket, recursive=True):
        if item.is_dir:
            continue
        target = safe_object_target(destination, item.object_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        client.fget_object(args.bucket, item.object_name, str(target))
        object_count += 1
        object_bytes += target.stat().st_size
    return {"event": "minio_download_completed", "object_count": object_count, "object_bytes": object_bytes}


def prepare(args: argparse.Namespace) -> dict[str, int | str]:
    client = make_client(args)
    if not client.bucket_exists(args.bucket):
        client.make_bucket(args.bucket)
    first_object = next(client.list_objects(args.bucket, recursive=True), None)
    if first_object is not None:
        raise ValueError("restore MinIO target is not empty")
    return {"event": "minio_restore_target_ready", "object_count": 0}


def upload(args: argparse.Namespace) -> dict[str, int | str]:
    client = make_client(args)
    source = Path(args.source).resolve()
    if not source.is_dir():
        raise ValueError(f"object source is not a directory: {source}")
    object_count = 0
    object_bytes = 0
    for item in sorted(path for path in source.rglob("*") if path.is_file()):
        object_name = item.relative_to(source).as_posix()
        content_type = mimetypes.guess_type(object_name)[0] or "application/octet-stream"
        client.fput_object(args.bucket, object_name, str(item), content_type=content_type)
        object_count += 1
        object_bytes += item.stat().st_size
    actual_count = sum(1 for item in client.list_objects(args.bucket, recursive=True) if not item.is_dir)
    if actual_count != object_count:
        raise ValueError("restored MinIO object count does not match uploaded file count")
    return {"event": "minio_upload_completed", "object_count": actual_count, "object_bytes": object_bytes}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--endpoint", required=True)
    common.add_argument("--bucket", required=True)
    common.add_argument("--access-key-file", required=True)
    common.add_argument("--secret-key-file", required=True)
    commands = result.add_subparsers(dest="command", required=True)
    download_parser = commands.add_parser("download", parents=[common])
    download_parser.add_argument("--destination", required=True)
    prepare_parser = commands.add_parser("prepare", parents=[common])
    upload_parser = commands.add_parser("upload", parents=[common])
    upload_parser.add_argument("--source", required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        handlers = {"download": download, "prepare": prepare, "upload": upload}
        print(json.dumps(handlers[args.command](args), separators=(",", ":")))
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI must convert SDK failures into a non-zero exit.
        print(f"MinIO operation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
