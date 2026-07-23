$ErrorActionPreference = "Stop"

docker compose build backend
if ($LASTEXITCODE -ne 0) { throw "Backend image failed to build." }

docker compose run --rm --no-deps backend python manage.py spectacular `
    --file /app/openapi/schema.json `
    --format openapi-json `
    --validate
if ($LASTEXITCODE -ne 0) { throw "OpenAPI schema generation failed." }

docker compose --profile tools build frontend-tools
if ($LASTEXITCODE -ne 0) { throw "Frontend tooling image failed to build." }

docker compose --profile tools run --rm --no-deps frontend-tools npm run generate:api
if ($LASTEXITCODE -ne 0) { throw "TypeScript client generation failed." }
