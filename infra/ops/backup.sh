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

if [[ "${BACKUP_TARGET_IS_OFFHOST:-0}" != "1" && "${ALLOW_LOCAL_BACKUP_TARGET:-0}" != "1" ]]; then
  printf 'backup target must be acknowledged as off-host; local target is drill-only\n' >&2
  exit 78
fi

for secret in backup_postgres_password backup_minio_access_key backup_minio_secret_key age_recipient.txt; do
  require_secret "${secret}"
done

: "${PGHOST:?PGHOST is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER is required}"
: "${MINIO_ENDPOINT:?MINIO_ENDPOINT is required}"
: "${MINIO_BUCKET:?MINIO_BUCKET is required}"

recovery_point="${RECOVERY_POINT_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
if [[ ! "${recovery_point}" =~ ^[0-9]{8}T[0-9]{6}Z$ ]]; then
  printf 'invalid RECOVERY_POINT_ID\n' >&2
  exit 64
fi

backup_root="/backups"
daily_dir="${backup_root}/daily"
work_root="$(mktemp -d /tmp/podoria-backup.XXXXXX)"
stage="${work_root}/podoria-${recovery_point}"
archive_name="podoria-${recovery_point}.tar.gz.age"
archive_path="${daily_dir}/${archive_name}"
partial_path="${archive_path}.partial"

cleanup() {
  rm -rf -- "${work_root}"
  rm -f -- "${partial_path}" "${archive_path}.sha256.partial" "${archive_path}.manifest.json.partial"
}
trap cleanup EXIT

mkdir -p -- "${stage}/objects" "${daily_dir}" "${backup_root}/monthly"
if [[ -e "${archive_path}" ]]; then
  printf 'recovery point already exists: %s\n' "${recovery_point}" >&2
  exit 73
fi

export PGPASSWORD
PGPASSWORD="$(< /run/secrets/backup_postgres_password)"
pg_dump \
  --host="${PGHOST}" \
  --port="${PGPORT:-5432}" \
  --username="${PGUSER}" \
  --dbname="${PGDATABASE}" \
  --format=custom \
  --compress=9 \
  --no-owner \
  --no-acl \
  --file="${stage}/postgres.dump"

object_report="$(minio_ops.py download \
  --endpoint "${MINIO_ENDPOINT}" \
  --bucket "${MINIO_BUCKET}" \
  --access-key-file /run/secrets/backup_minio_access_key \
  --secret-key-file /run/secrets/backup_minio_secret_key \
  --destination "${stage}/objects")"

migration_count="$(psql --host="${PGHOST}" --port="${PGPORT:-5432}" \
  --username="${PGUSER}" --dbname="${PGDATABASE}" --tuples-only --no-align \
  --command='SELECT COUNT(*) FROM django_migrations')"
object_count="$(json_ops.py get object_count <<< "${object_report}")"
object_bytes="$(json_ops.py get object_bytes <<< "${object_report}")"
dump_bytes="$(stat -c %s "${stage}/postgres.dump")"

(
  cd "${stage}"
  find postgres.dump objects -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
json_ops.py write \
  --output "${stage}/manifest.json" \
  --integer format_version=1 \
  --string "recovery_point=${recovery_point}" \
  --string "created_at=${created_at}" \
  --string "database=${PGDATABASE}" \
  --string "bucket=${MINIO_BUCKET}" \
  --integer "migration_count=${migration_count}" \
  --integer "object_count=${object_count}" \
  --integer "object_bytes=${object_bytes}" \
  --integer "postgres_dump_bytes=${dump_bytes}"

tar -C "${work_root}" -czf "${work_root}/payload.tar.gz" "podoria-${recovery_point}"
age -R /run/secrets/age_recipient.txt -o "${partial_path}" "${work_root}/payload.tar.gz"
if [[ ! -s "${partial_path}" ]]; then
  printf 'encrypted archive is empty\n' >&2
  exit 74
fi

cp "${stage}/manifest.json" "${archive_path}.manifest.json.partial"
(
  cd "${daily_dir}"
  archive_sha256="$(sha256sum "${archive_name}.partial" | cut -d ' ' -f1)"
  printf '%s  %s\n' "${archive_sha256}" "${archive_name}" > "${archive_name}.sha256.partial"
)
mv -- "${archive_path}.manifest.json.partial" "${archive_path}.manifest.json"
mv -- "${archive_path}.sha256.partial" "${archive_path}.sha256"
mv -- "${partial_path}" "${archive_path}"

RETENTION_PROMOTE_FILE="${archive_path}" /usr/local/bin/retention.sh >/dev/null

archive_bytes="$(stat -c %s "${archive_path}")"
archive_sha256="$(cut -d ' ' -f1 "${archive_path}.sha256")"
json_ops.py write \
  --string event=backup_completed \
  --string "recovery_point=${recovery_point}" \
  --integer "archive_bytes=${archive_bytes}" \
  --string "archive_sha256=${archive_sha256}" \
  --integer "migration_count=${migration_count}" \
  --integer "object_count=${object_count}"
