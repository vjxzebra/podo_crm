#!/bin/sh
set -eu

BASE_DIR=${PODORIA_BASE_DIR:-/opt/podoria-crm}
PROJECT_NAME=${COMPOSE_PROJECT_NAME:-podoria-production}
EDGE_NETWORK_NAME=${EDGE_NETWORK_NAME:-podoria-edge}
SHARED_DIR="$BASE_DIR/shared"
SECRETS_DIR="$BASE_DIR/secrets"
RELEASES_DIR="$BASE_DIR/releases"
STATE_DIR="$BASE_DIR/state"
ENV_FILE="$SHARED_DIR/production.env"

usage() {
  echo "Usage: $0 <40-char-commit-sha> <source.tar.gz> <images.tar.gz>" >&2
  exit 2
}

[ "$#" -eq 3 ] || usage
RELEASE_SHA=$1
SOURCE_ARCHIVE=$2
IMAGE_ARCHIVE=$3

if [ "${#RELEASE_SHA}" -ne 40 ] \
  || ! printf '%s' "$RELEASE_SHA" | grep -Eq '^[0-9a-f]{40}$'
then
  echo "Release SHA must contain exactly 40 lowercase hexadecimal characters." >&2
  exit 2
fi

[ -s "$SOURCE_ARCHIVE" ] || { echo "Source archive is missing or empty." >&2; exit 2; }
[ -s "$IMAGE_ARCHIVE" ] || { echo "Image archive is missing or empty." >&2; exit 2; }
[ -s "$ENV_FILE" ] || { echo "Production environment file is missing." >&2; exit 2; }

for secret_name in \
  django_secret_key postgres_app_password postgres_backup_user postgres_backup_password \
  minio_root_user minio_root_password minio_app_access_key minio_app_secret_key \
  minio_backup_access_key minio_backup_secret_key
do
  [ -s "$SECRETS_DIR/$secret_name" ] || {
    echo "Required production secret is missing: $secret_name" >&2
    exit 2
  }
done

if [ -f "$SOURCE_ARCHIVE.sha256" ]; then
  (cd "$(dirname "$SOURCE_ARCHIVE")" && sha256sum -c "$(basename "$SOURCE_ARCHIVE").sha256")
fi
if [ -f "$IMAGE_ARCHIVE.sha256" ]; then
  (cd "$(dirname "$IMAGE_ARCHIVE")" && sha256sum -c "$(basename "$IMAGE_ARCHIVE").sha256")
fi

if tar -tzf "$SOURCE_ARCHIVE" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
  echo "Source archive contains an unsafe path." >&2
  exit 2
fi

mkdir -p "$RELEASES_DIR" "$STATE_DIR"
RELEASE_DIR="$RELEASES_DIR/$RELEASE_SHA"
if [ ! -d "$RELEASE_DIR" ]; then
  PARTIAL_RELEASE="$RELEASE_DIR.partial.$$"
  trap 'rm -rf "$PARTIAL_RELEASE"' EXIT HUP INT TERM
  mkdir -p "$PARTIAL_RELEASE"
  tar -xzf "$SOURCE_ARCHIVE" -C "$PARTIAL_RELEASE"
  printf '%s\n' "$RELEASE_SHA" > "$PARTIAL_RELEASE/.release-sha"
  mv "$PARTIAL_RELEASE" "$RELEASE_DIR"
  trap - EXIT HUP INT TERM
elif [ "$(cat "$RELEASE_DIR/.release-sha" 2>/dev/null || true)" != "$RELEASE_SHA" ]; then
  echo "Existing release directory does not match the requested SHA." >&2
  exit 2
fi

for required_file in compose.production.yaml compose.edge.yaml infra/nginx/default.conf; do
  [ -f "$RELEASE_DIR/$required_file" ] || {
    echo "Release is missing required file: $required_file" >&2
    exit 2
  }
done

gzip -dc "$IMAGE_ARCHIVE" | docker load >/dev/null
BACKEND_TAG="podoria-crm-backend:$RELEASE_SHA"
WEB_TAG="podoria-crm-web:$RELEASE_SHA"
BACKEND_IMAGE=$(docker image inspect "$BACKEND_TAG" --format '{{.Id}}')
WEB_IMAGE=$(docker image inspect "$WEB_TAG" --format '{{.Id}}')

docker network inspect "$EDGE_NETWORK_NAME" >/dev/null 2>&1 \
  || docker network create "$EDGE_NETWORK_NAME" >/dev/null

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a
export COMPOSE_PROJECT_NAME="$PROJECT_NAME"
export EDGE_NETWORK_NAME
export PODORIA_SECRET_DIR="$SECRETS_DIR"
export BACKEND_IMAGE
export WEB_IMAGE

compose() {
  docker compose \
    --env-file "$ENV_FILE" \
    -f "$RELEASE_DIR/compose.production.yaml" \
    -f "$RELEASE_DIR/compose.edge.yaml" \
    "$@"
}

CURRENT_RELEASE=$(readlink -f "$BASE_DIR/current" 2>/dev/null || true)
PREVIOUS_BACKEND_IMAGE=$(docker inspect "$PROJECT_NAME-backend-1" --format '{{.Image}}' 2>/dev/null || true)
PREVIOUS_WEB_IMAGE=$(docker inspect "$PROJECT_NAME-web-1" --format '{{.Image}}' 2>/dev/null || true)
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
STATE_PARTIAL="$STATE_DIR/$RELEASE_SHA.partial.json"

write_state() {
  status=$1
  error_message=${2:-}
  umask 077
  printf '%s\n' \
    "{" \
    "  \"release_sha\": \"$RELEASE_SHA\"," \
    "  \"status\": \"$status\"," \
    "  \"started_at\": \"$STARTED_AT\"," \
    "  \"completed_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," \
    "  \"backend_image\": \"$BACKEND_IMAGE\"," \
    "  \"web_image\": \"$WEB_IMAGE\"," \
    "  \"previous_backend_image\": \"$PREVIOUS_BACKEND_IMAGE\"," \
    "  \"previous_web_image\": \"$PREVIOUS_WEB_IMAGE\"," \
    "  \"previous_release\": \"$CURRENT_RELEASE\"," \
    "  \"error\": \"$error_message\"" \
    "}" > "$STATE_PARTIAL"
}

rollback_candidate() {
  [ -n "$CURRENT_RELEASE" ] || return 0
  [ -n "$PREVIOUS_BACKEND_IMAGE" ] || return 0
  [ -n "$PREVIOUS_WEB_IMAGE" ] || return 0
  [ -f "$CURRENT_RELEASE/compose.production.yaml" ] || return 0
  export BACKEND_IMAGE="$PREVIOUS_BACKEND_IMAGE"
  export WEB_IMAGE="$PREVIOUS_WEB_IMAGE"
  docker compose \
    --env-file "$ENV_FILE" \
    -f "$CURRENT_RELEASE/compose.production.yaml" \
    -f "$CURRENT_RELEASE/compose.edge.yaml" \
    up -d --no-deps backend web worker beat proxy >/dev/null 2>&1 || true
  /usr/local/sbin/podoria-caddy-reconcile >/dev/null 2>&1 || true
}

deploy_failed() {
  exit_code=$?
  trap - EXIT HUP INT TERM
  rollback_candidate
  write_state failed "deployment command failed"
  mv "$STATE_PARTIAL" "$STATE_DIR/$RELEASE_SHA.failed.json"
  exit "$exit_code"
}
trap deploy_failed EXIT HUP INT TERM

curl -fsS --resolve rozhenko.km.ua:443:127.0.0.1 https://rozhenko.km.ua/ >/dev/null
compose config --quiet
compose up -d --wait postgres redis minio
compose run --rm minio-init
compose --profile deploy run --rm --no-deps migrate
compose run --rm --no-deps backend python manage.py check --deploy
compose up -d --no-deps --wait backend web
compose up -d --no-deps worker beat
compose up -d --no-deps --force-recreate --wait proxy
/usr/local/sbin/podoria-caddy-reconcile

curl -fsS http://127.0.0.1:8088/health/ready >/dev/null
attempt=0
until curl -fsS --resolve crm.rozhenko.km.ua:443:127.0.0.1 \
  https://crm.rozhenko.km.ua/health/ready >/dev/null
do
  attempt=$((attempt + 1))
  [ "$attempt" -lt 30 ] || {
    echo "CRM HTTPS readiness did not become healthy." >&2
    exit 1
  }
  sleep 2
done
curl -fsS --resolve rozhenko.km.ua:443:127.0.0.1 https://rozhenko.km.ua/ >/dev/null
session_status=$(curl -sS -o /dev/null -w '%{http_code}' \
  --resolve crm.rozhenko.km.ua:443:127.0.0.1 \
  https://crm.rozhenko.km.ua/api/v1/session)
[ "$session_status" = "401" ] || {
  echo "Unauthenticated session smoke returned $session_status instead of 401." >&2
  exit 1
}

if [ "${CONFIGURE_TELEGRAM_WEBHOOK:-0}" = "1" ]; then
  compose run --rm --no-deps backend python manage.py configure_telegram_webhook
fi

ln -sfn "$RELEASE_DIR" "$BASE_DIR/current.next"
mv -Tf "$BASE_DIR/current.next" "$BASE_DIR/current"
write_state deployed
mv "$STATE_PARTIAL" "$STATE_DIR/$RELEASE_SHA.json"
trap - EXIT HUP INT TERM

rm -f "$SOURCE_ARCHIVE" "$SOURCE_ARCHIVE.sha256" "$IMAGE_ARCHIVE" "$IMAGE_ARCHIVE.sha256"
printf '{"release_sha":"%s","status":"deployed","readiness":200,"session":401}\n' "$RELEASE_SHA"
