#!/bin/sh
set -eu

BASE_DIR=${PODORIA_BASE_DIR:-/opt/podoria-crm}
ENV_FILE="$BASE_DIR/shared/production.env"
SECRETS_DIR="$BASE_DIR/secrets"
CURRENT_RELEASE=$(readlink -f "$BASE_DIR/current" 2>/dev/null || true)

[ "$(id -u)" -eq 0 ] || {
  echo "Production demo seeding must run as root." >&2
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

docker compose \
  --env-file "$ENV_FILE" \
  -f "$CURRENT_RELEASE/compose.production.yaml" \
  -f "$CURRENT_RELEASE/compose.edge.yaml" \
  run --rm --no-deps backend \
  python manage.py seed_demo_data "$@"

curl -fsS --resolve crm.rozhenko.km.ua:443:127.0.0.1 \
  https://crm.rozhenko.km.ua/health/ready >/dev/null
