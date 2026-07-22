param(
    [Parameter(Mandatory = $true)][string]$BackendImage,
    [Parameter(Mandatory = $true)][string]$WebImage,
    [Parameter(Mandatory = $true)][string]$PreviousBackendImage,
    [Parameter(Mandatory = $true)][string]$PreviousWebImage,
    [Parameter(Mandatory = $true)][string]$SecretDirectory,
    [Parameter(Mandatory = $true)][string]$StatePath,
    [Parameter(Mandatory = $true)][string]$RecoveryPointId,
    [Parameter(Mandatory = $true)][string]$RecoveryPointManifestPath,
    [string]$ProjectName = "podoria-production",
    [int]$AppPort = 8088,
    [string]$AllowedHosts = "localhost,127.0.0.1,backend,proxy",
    [string]$CsrfTrustedOrigins = "https://localhost",
    [switch]$DisableSslRedirectForRehearsal
)

$ErrorActionPreference = "Stop"

function Assert-ImmutableImage([string]$Reference) {
    if ($Reference -notmatch '^sha256:[0-9a-f]{64}$' -and $Reference -notmatch '@sha256:[0-9a-f]{64}$') {
        throw "Image reference must be immutable (image id or digest): $Reference"
    }
    docker image inspect $Reference | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Image is not available locally: $Reference" }
}

Assert-ImmutableImage $BackendImage
Assert-ImmutableImage $WebImage
Assert-ImmutableImage $PreviousBackendImage
Assert-ImmutableImage $PreviousWebImage

$secrets = [System.IO.Path]::GetFullPath($SecretDirectory)
$state = [System.IO.Path]::GetFullPath($StatePath)
foreach ($name in @(
    "django_secret_key", "postgres_app_password", "postgres_backup_user",
    "postgres_backup_password", "minio_root_user", "minio_root_password",
    "minio_app_access_key", "minio_app_secret_key", "minio_backup_access_key",
    "minio_backup_secret_key"
)) {
    $path = Join-Path $secrets $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -eq 0) {
        throw "Required production secret file is missing or empty: $name"
    }
}
if (Test-Path -LiteralPath $state) { throw "Deployment state already exists: $state" }
$recoveryManifestPath = [System.IO.Path]::GetFullPath($RecoveryPointManifestPath)
if (-not (Test-Path -LiteralPath $recoveryManifestPath -PathType Leaf)) {
    throw "Recovery point manifest does not exist: $recoveryManifestPath"
}
$recoveryManifest = Get-Content -LiteralPath $recoveryManifestPath -Raw | ConvertFrom-Json
if ($recoveryManifest.format_version -ne 1 -or $recoveryManifest.recovery_point -ne $RecoveryPointId) {
    throw "Recovery point manifest does not match the requested release preflight."
}

$env:COMPOSE_PROJECT_NAME = $ProjectName
$env:BACKEND_IMAGE = $BackendImage
$env:WEB_IMAGE = $WebImage
$env:PODORIA_SECRET_DIR = $secrets
$env:APP_PORT = $AppPort.ToString()
$env:DJANGO_ALLOWED_HOSTS = $AllowedHosts
$env:DJANGO_CSRF_TRUSTED_ORIGINS = $CsrfTrustedOrigins
$env:DJANGO_SECURE_SSL_REDIRECT = if ($DisableSslRedirectForRehearsal) { "0" } else { "1" }
$compose = @("compose", "-f", "compose.production.yaml", "--profile", "deploy")

$deployment = [ordered]@{
    status = "started"
    started_at = (Get-Date).ToUniversalTime().ToString("o")
    recovery_point = $RecoveryPointId
    previous_backend_image = $PreviousBackendImage
    previous_web_image = $PreviousWebImage
    candidate_backend_image = $BackendImage
    candidate_web_image = $WebImage
    project = $ProjectName
    app_port = $AppPort
}
$stateDirectory = Split-Path -Parent $state
if (-not (Test-Path -LiteralPath $stateDirectory)) {
    New-Item -ItemType Directory -Force $stateDirectory | Out-Null
}
$deployment | ConvertTo-Json | Set-Content -LiteralPath "$state.partial" -Encoding utf8NoBOM

try {
    & docker @compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Production Compose preflight failed." }
    & docker @compose up -d --wait postgres redis minio
    if ($LASTEXITCODE -ne 0) { throw "Production dependencies failed to become healthy." }
    & docker @compose run --rm minio-init
    if ($LASTEXITCODE -ne 0) { throw "MinIO identity/bucket provisioning failed." }
    & docker @compose run --rm --no-deps migrate
    if ($LASTEXITCODE -ne 0) { throw "Migration job failed." }
    & docker @compose run --rm --no-deps backend python manage.py check --deploy
    if ($LASTEXITCODE -ne 0) { throw "Candidate deploy check failed." }
    & docker @compose up -d --no-deps --wait backend web
    if ($LASTEXITCODE -ne 0) { throw "Candidate web/backend failed to become healthy." }
    & docker @compose up -d --no-deps worker beat
    if ($LASTEXITCODE -ne 0) { throw "Candidate background services failed to start." }
    & docker @compose up -d --no-deps --force-recreate --wait proxy
    if ($LASTEXITCODE -ne 0) { throw "Proxy switch failed." }

    $root = (Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$AppPort/" -TimeoutSec 10).StatusCode
    $ready = (Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$AppPort/health/ready" -TimeoutSec 10).StatusCode
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$AppPort/api/v1/session" -TimeoutSec 10 | Out-Null
        $session = 200
    }
    catch {
        $session = [int]$_.Exception.Response.StatusCode
    }
    if ($root -ne 200 -or $ready -ne 200 -or $session -ne 401) {
        throw "Deployment smoke failed: root=$root ready=$ready session=$session"
    }
    $deployment.status = "deployed"
    $deployment.completed_at = (Get-Date).ToUniversalTime().ToString("o")
    $deployment.smoke = @{ root = $root; readiness = $ready; unauthenticated_session = $session }
    $deployment | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$state.partial" -Encoding utf8NoBOM
    Move-Item -LiteralPath "$state.partial" -Destination $state
}
catch {
    $deployment.status = "failed"
    $deployment.error = $_.Exception.Message
    $deployment | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$state.failed" -Encoding utf8NoBOM
    throw
}
