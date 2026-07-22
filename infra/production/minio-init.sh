#!/bin/sh
set -eu

bucket="${MINIO_BUCKET_NAME}"
case "${bucket}" in
  *[!a-z0-9.-]*|'') echo "invalid MINIO_BUCKET_NAME" >&2; exit 64 ;;
esac

root_user="$(cat /run/secrets/minio_root_user)"
root_password="$(cat /run/secrets/minio_root_password)"
app_access="$(cat /run/secrets/minio_app_access_key)"
app_secret="$(cat /run/secrets/minio_app_secret_key)"
backup_access="$(cat /run/secrets/minio_backup_access_key)"
backup_secret="$(cat /run/secrets/minio_backup_secret_key)"

mc alias set primary http://minio:9000 "${root_user}" "${root_password}" >/dev/null
mc mb --ignore-existing "primary/${bucket}" >/dev/null
mc anonymous set private "primary/${bucket}" >/dev/null

render_policy() {
  source_path="$1"
  target_path="$2"
  : > "${target_path}"
  while IFS= read -r line || [ -n "${line}" ]; do
    line_prefix="${line%%__BUCKET__*}"
    if [ "${line_prefix}" != "${line}" ]; then
      line_suffix="${line#*__BUCKET__}"
      line="${line_prefix}${bucket}${line_suffix}"
    fi
    printf '%s\n' "${line}" >> "${target_path}"
  done < "${source_path}"
}

render_policy /policies/app.json /tmp/app-policy.json
render_policy /policies/backup.json /tmp/backup-policy.json
mc admin policy create primary podoria-app /tmp/app-policy.json >/dev/null
mc admin policy create primary podoria-backup /tmp/backup-policy.json >/dev/null
mc admin user add primary "${app_access}" "${app_secret}" >/dev/null
mc admin user add primary "${backup_access}" "${backup_secret}" >/dev/null
mc admin policy attach primary podoria-app --user "${app_access}" >/dev/null
mc admin policy attach primary podoria-backup --user "${backup_access}" >/dev/null
