param(
    [Parameter(Mandatory = $true)][string]$StatePath,
    [Parameter(Mandatory = $true)][string]$SecretDirectory,
    [switch]$DisableSslRedirectForRehearsal
)

$ErrorActionPreference = "Stop"
$state = [System.IO.Path]::GetFullPath($StatePath)
if (-not (Test-Path -LiteralPath $state -PathType Leaf)) {
    throw "Deployment state does not exist: $state"
}
$deployment = Get-Content -LiteralPath $state -Raw | ConvertFrom-Json
if ($deployment.status -ne "deployed") { throw "Only a completed deployment can be rolled back." }

$env:COMPOSE_PROJECT_NAME = $deployment.project
$env:BACKEND_IMAGE = $deployment.previous_backend_image
$env:WEB_IMAGE = $deployment.previous_web_image
$env:PODORIA_SECRET_DIR = [System.IO.Path]::GetFullPath($SecretDirectory)
$env:APP_PORT = $deployment.app_port.ToString()
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,backend,proxy"
$env:DJANGO_CSRF_TRUSTED_ORIGINS = "https://localhost"
$env:DJANGO_SECURE_SSL_REDIRECT = if ($DisableSslRedirectForRehearsal) { "0" } else { "1" }
$compose = @("compose", "-f", "compose.production.yaml")

foreach ($image in @($env:BACKEND_IMAGE, $env:WEB_IMAGE)) {
    docker image inspect $image | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Rollback image is unavailable: $image" }
}

& docker @compose up -d --no-deps --force-recreate --wait backend web
if ($LASTEXITCODE -ne 0) { throw "Rollback web/backend failed to become healthy." }
& docker @compose up -d --no-deps --force-recreate worker beat
if ($LASTEXITCODE -ne 0) { throw "Rollback background services failed to start." }
& docker @compose up -d --no-deps --force-recreate --wait proxy
if ($LASTEXITCODE -ne 0) { throw "Rollback proxy switch failed." }

$root = (Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$($deployment.app_port)/" -TimeoutSec 10).StatusCode
$ready = (Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$($deployment.app_port)/health/ready" -TimeoutSec 10).StatusCode
try {
    Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$($deployment.app_port)/api/v1/session" -TimeoutSec 10 | Out-Null
    $session = 200
}
catch {
    $session = [int]$_.Exception.Response.StatusCode
}
if ($root -ne 200 -or $ready -ne 200 -or $session -ne 401) {
    throw "Rollback smoke failed: root=$root ready=$ready session=$session"
}

$deployment.status = "rolled_back"
$deployment | Add-Member -NotePropertyName rolled_back_at -NotePropertyValue ((Get-Date).ToUniversalTime().ToString("o")) -Force
$deployment | Add-Member -NotePropertyName rollback_smoke -NotePropertyValue @{
    root = $root
    readiness = $ready
    unauthenticated_session = $session
} -Force
$deployment | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $state -Encoding utf8NoBOM
