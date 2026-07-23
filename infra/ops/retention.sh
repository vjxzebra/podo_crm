#!/usr/bin/env bash
set -euo pipefail

backup_root="/backups"
daily_dir="${backup_root}/daily"
monthly_dir="${backup_root}/monthly"
daily_keep="${BACKUP_DAILY_KEEP:-30}"
monthly_keep="${BACKUP_MONTHLY_KEEP:-12}"
mkdir -p -- "${daily_dir}" "${monthly_dir}"

if [[ ! "${daily_keep}" =~ ^[1-9][0-9]*$ || ! "${monthly_keep}" =~ ^[1-9][0-9]*$ ]]; then
  printf 'retention values must be positive integers\n' >&2
  exit 64
fi

promote_file="${RETENTION_PROMOTE_FILE:-}"
if [[ -n "${promote_file}" ]]; then
  promote_file="$(realpath -e "${promote_file}")"
  case "${promote_file}" in
    "${daily_dir}"/podoria-*.tar.gz.age) ;;
    *) printf 'monthly promotion source is invalid\n' >&2; exit 64 ;;
  esac
  recovery_name="$(basename "${promote_file}")"
  recovery_month="${recovery_name#podoria-}"
  recovery_month="${recovery_month:0:6}"
  if [[ "${BACKUP_PROMOTE_MONTHLY:-0}" == "1" || "${recovery_name:14:2}" == "01" ]]; then
    if ! compgen -G "${monthly_dir}/podoria-${recovery_month}*.tar.gz.age" >/dev/null; then
      cp -- "${promote_file}" "${monthly_dir}/${recovery_name}"
      cp -- "${promote_file}.sha256" "${monthly_dir}/${recovery_name}.sha256"
      cp -- "${promote_file}.manifest.json" "${monthly_dir}/${recovery_name}.manifest.json"
    fi
  fi
fi

prune_directory() {
  local directory="$1"
  local keep="$2"
  local -a archives
  mapfile -t archives < <(find "${directory}" -maxdepth 1 -type f -name 'podoria-*.tar.gz.age' -printf '%f\n' | sort -r)
  if (( ${#archives[@]} <= keep )); then
    return
  fi
  local archive
  for archive in "${archives[@]:keep}"; do
    if [[ "${RETENTION_DRY_RUN:-0}" == "1" ]]; then
      printf 'would_remove=%s/%s\n' "${directory}" "${archive}"
    else
      rm -f -- \
        "${directory}/${archive}" \
        "${directory}/${archive}.sha256" \
        "${directory}/${archive}.manifest.json"
    fi
  done
}

prune_directory "${daily_dir}" "${daily_keep}"
prune_directory "${monthly_dir}" "${monthly_keep}"
printf '{"event":"retention_completed","daily_keep":%s,"monthly_keep":%s,"dry_run":%s}\n' \
  "${daily_keep}" "${monthly_keep}" "$( [[ "${RETENTION_DRY_RUN:-0}" == "1" ]] && printf true || printf false )"
