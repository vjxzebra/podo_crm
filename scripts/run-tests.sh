#!/bin/sh
set -eu

cleanup() {
  docker compose --profile test rm -sf test-postgres >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose --profile test build backend-test frontend-test
docker compose --profile test up -d --wait test-postgres
docker compose --profile test run --rm --no-deps backend-test
docker compose --profile test run --rm --no-deps frontend-test
