#!/bin/sh
set -eu

BASE_DIR=${PODORIA_BASE_DIR:-/opt/podoria-crm}
ENV_FILE="$BASE_DIR/shared/production.env"
SECRETS_DIR="$BASE_DIR/secrets"
CURRENT_RELEASE=$(readlink -f "$BASE_DIR/current" 2>/dev/null || true)
CONFIRMATION=
WITH_ADMIN=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --confirm)
      [ "$#" -ge 2 ] || { echo "--confirm requires a value." >&2; exit 2; }
      CONFIRMATION=$2
      shift 2
      ;;
    --with-admin)
      WITH_ADMIN=1
      shift
      ;;
    *)
      echo "Usage: $0 --confirm RESET_PODORIA_CRM_DATABASE [--with-admin]" >&2
      exit 2
      ;;
  esac
done

[ "$CONFIRMATION" = "RESET_PODORIA_CRM_DATABASE" ] || {
  echo "Exact confirmation token RESET_PODORIA_CRM_DATABASE is required." >&2
  exit 2
}
[ -n "$CURRENT_RELEASE" ] && [ -d "$CURRENT_RELEASE" ] || {
  echo "Current production release is missing." >&2
  exit 2
}
case "$CURRENT_RELEASE" in
  "$BASE_DIR"/releases/*) ;;
  *) echo "Current release resolves outside the production releases directory." >&2; exit 2 ;;
esac
[ -s "$ENV_FILE" ] || { echo "Production environment file is missing." >&2; exit 2; }

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a
COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-podoria-production}
EDGE_NETWORK_NAME=${EDGE_NETWORK_NAME:-podoria-edge}
PODORIA_SECRET_DIR="$SECRETS_DIR"
BACKEND_IMAGE=$(docker inspect "$COMPOSE_PROJECT_NAME-backend-1" --format '{{.Image}}')
WEB_IMAGE=$(docker inspect "$COMPOSE_PROJECT_NAME-web-1" --format '{{.Image}}')
export COMPOSE_PROJECT_NAME EDGE_NETWORK_NAME PODORIA_SECRET_DIR BACKEND_IMAGE WEB_IMAGE

POSTGRES_DB=${POSTGRES_DB:-podoria}
POSTGRES_USER=${POSTGRES_USER:-podoria}
if ! printf '%s' "$POSTGRES_DB" | grep -Eq '^[A-Za-z_][A-Za-z0-9_]*$'; then
  echo "POSTGRES_DB is not a safe SQL identifier." >&2
  exit 2
fi
if ! printf '%s' "$POSTGRES_USER" | grep -Eq '^[A-Za-z_][A-Za-z0-9_]*$'; then
  echo "POSTGRES_USER is not a safe SQL identifier." >&2
  exit 2
fi

compose() {
  docker compose \
    --env-file "$ENV_FILE" \
    -f "$CURRENT_RELEASE/compose.production.yaml" \
    -f "$CURRENT_RELEASE/compose.edge.yaml" \
    "$@"
}

compose up -d --wait postgres redis minio
RESET_DIR="$BASE_DIR/resets"
mkdir -p "$RESET_DIR"
umask 077
BACKUP_PATH="$RESET_DIR/pre-reset-$(date -u +%Y%m%dT%H%M%SZ).dump"
compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$BACKUP_PATH"
[ -s "$BACKUP_PATH" ] || { echo "Pre-reset database snapshot is empty." >&2; exit 1; }

compose stop proxy worker beat backend
compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres <<SQL
DROP DATABASE IF EXISTS "$POSTGRES_DB" WITH (FORCE);
CREATE DATABASE "$POSTGRES_DB" OWNER "$POSTGRES_USER";
SQL
compose exec -T redis redis-cli FLUSHDB >/dev/null
compose --profile deploy run --rm --no-deps migrate

if [ "$WITH_ADMIN" -eq 1 ]; then
  ADMIN_CREDENTIALS="$SECRETS_DIR/initial_admin_credentials"
  [ -s "$ADMIN_CREDENTIALS" ] || {
    echo "Initial administrator credentials file is missing." >&2
    exit 1
  }
  compose run --rm --no-deps \
    -v "$ADMIN_CREDENTIALS:/run/secrets/initial_admin_credentials:ro" \
    backend python manage.py provision_initial_admin \
      --credentials-file /run/secrets/initial_admin_credentials
fi

compose up -d --no-deps --wait backend web
compose up -d --no-deps worker beat
compose up -d --no-deps --force-recreate --wait proxy
/usr/local/sbin/podoria-caddy-reconcile
curl -fsS --resolve crm.rozhenko.km.ua:443:127.0.0.1 \
  https://crm.rozhenko.km.ua/health/ready >/dev/null

printf '{"status":"reset","backup":"%s","admin_provisioned":%s}\n' \
  "$BACKUP_PATH" "$WITH_ADMIN"
