#!/usr/bin/env bash
set -euo pipefail
umask 077

require_secret() {
  local path="/run/secrets/$1"
  if [[ ! -s "${path}" ]]; then
    printf 'required secret file is missing or empty: %s\n' "${path}" >&2
    exit 78
  fi
}

for secret in restore_postgres_password restore_minio_access_key restore_minio_secret_key age_identity.txt; do
  require_secret "${secret}"
done

: "${RECOVERY_POINT_FILE:?RECOVERY_POINT_FILE is required}"
: "${PGHOST:?PGHOST is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER is required}"
: "${MINIO_ENDPOINT:?MINIO_ENDPOINT is required}"
: "${MINIO_BUCKET:?MINIO_BUCKET is required}"

archive_path="$(realpath -e "${RECOVERY_POINT_FILE}")"
case "${archive_path}" in
  /backups/daily/podoria-*.tar.gz.age|/backups/monthly/podoria-*.tar.gz.age) ;;
  *)
    printf 'recovery point must be a validated archive below /backups/daily or /backups/monthly\n' >&2
    exit 64
    ;;
esac

archive_name="$(basename "${archive_path}")"
recovery_point="${archive_name#podoria-}"
recovery_point="${recovery_point%.tar.gz.age}"
if [[ "${RESTORE_CONFIRM:-}" != "restore:${recovery_point}" ]]; then
  printf 'RESTORE_CONFIRM must equal restore:%s\n' "${recovery_point}" >&2
  exit 78
fi
if [[ "${RESTORE_ALLOW_REPLACE:-0}" == "1" ]]; then
  printf 'replace restore is incident-only and intentionally not automated; use an empty isolated target\n' >&2
  exit 78
fi

sidecar_sha="${archive_path}.sha256"
sidecar_manifest="${archive_path}.manifest.json"
if [[ ! -s "${sidecar_sha}" || ! -s "${sidecar_manifest}" ]]; then
  printf 'recovery point sidecars are missing\n' >&2
  exit 65
fi
(
  cd "$(dirname "${archive_path}")"
  sha256sum -c "$(basename "${sidecar_sha}")" >/dev/null
)

work_root="$(mktemp -d /tmp/podoria-restore.XXXXXX)"
cleanup() {
  rm -rf -- "${work_root}"
}
trap cleanup EXIT

age --decrypt -i /run/secrets/age_identity.txt -o "${work_root}/payload.tar.gz" "${archive_path}"
tar -tzf "${work_root}/payload.tar.gz" > "${work_root}/entries"
if awk 'BEGIN{bad=0} /^\//{bad=1} $0 ~ /(^|\/)\.\.($|\/)/{bad=1} END{exit bad ? 0 : 1}' "${work_root}/entries"; then
  printf 'unsafe archive path rejected\n' >&2
  exit 65
fi
tar -xzf "${work_root}/payload.tar.gz" -C "${work_root}"
stage="${work_root}/podoria-${recovery_point}"
if [[ ! -s "${stage}/manifest.json" || ! -s "${stage}/SHA256SUMS" || ! -s "${stage}/postgres.dump" ]]; then
  printf 'recovery payload is incomplete\n' >&2
  exit 65
fi
if [[ "$(json_ops.py get recovery_point --file "${stage}/manifest.json")" != "${recovery_point}" ]]; then
  printf 'manifest recovery point mismatch\n' >&2
  exit 65
fi
(
  cd "${stage}"
  sha256sum -c SHA256SUMS >/dev/null
)

export PGPASSWORD
PGPASSWORD="$(< /run/secrets/restore_postgres_password)"
table_count="$(psql --host="${PGHOST}" --port="${PGPORT:-5432}" \
  --username="${PGUSER}" --dbname="${PGDATABASE}" --tuples-only --no-align \
  --command="SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")"
if [[ "${table_count}" != "0" ]]; then
  printf 'restore PostgreSQL target is not empty\n' >&2
  exit 78
fi

minio_ops.py prepare \
  --endpoint "${MINIO_ENDPOINT}" \
  --bucket "${MINIO_BUCKET}" \
  --access-key-file /run/secrets/restore_minio_access_key \
  --secret-key-file /run/secrets/restore_minio_secret_key >/dev/null

pg_restore \
  --host="${PGHOST}" \
  --port="${PGPORT:-5432}" \
  --username="${PGUSER}" \
  --dbname="${PGDATABASE}" \
  --exit-on-error \
  --no-owner \
  --no-acl \
  "${stage}/postgres.dump"
object_report="$(minio_ops.py upload \
  --endpoint "${MINIO_ENDPOINT}" \
  --bucket "${MINIO_BUCKET}" \
  --access-key-file /run/secrets/restore_minio_access_key \
  --secret-key-file /run/secrets/restore_minio_secret_key \
  --source "${stage}/objects")"

expected_objects="$(json_ops.py get object_count --file "${stage}/manifest.json")"
actual_objects="$(json_ops.py get object_count <<< "${object_report}")"
expected_migrations="$(json_ops.py get migration_count --file "${stage}/manifest.json")"
actual_migrations="$(psql --host="${PGHOST}" --port="${PGPORT:-5432}" \
  --username="${PGUSER}" --dbname="${PGDATABASE}" --tuples-only --no-align \
  --command='SELECT COUNT(*) FROM django_migrations')"
if [[ "${actual_objects}" != "${expected_objects}" || "${actual_migrations}" != "${expected_migrations}" ]]; then
  printf 'restored counts do not match manifest\n' >&2
  exit 65
fi

json_ops.py write \
  --string event=restore_completed \
  --string "recovery_point=${recovery_point}" \
  --integer "migration_count=${actual_migrations}" \
  --integer "object_count=${actual_objects}"
