$ErrorActionPreference = "Stop"

try {
    docker compose --profile test build backend-test frontend-test
    if ($LASTEXITCODE -ne 0) { throw "Test images failed to build." }

    docker compose --profile test up -d --wait test-postgres
    if ($LASTEXITCODE -ne 0) { throw "Test PostgreSQL failed to start." }

    docker compose --profile test run --rm --no-deps backend-test
    if ($LASTEXITCODE -ne 0) { throw "Backend quality gate failed." }

    docker compose --profile test run --rm --no-deps frontend-test
    if ($LASTEXITCODE -ne 0) { throw "Frontend quality gate failed." }
}
finally {
    docker compose --profile test rm -sf test-postgres | Out-Null
}
