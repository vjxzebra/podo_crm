param(
    [Parameter(Mandatory = $true)][string]$TargetPath,
    [Parameter(Mandatory = $true)][string]$SecretDirectory,
    [string]$RecoveryPointId = "",
    [switch]$OffHost,
    [switch]$LocalRehearsal,
    [switch]$PromoteMonthly
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$target = [System.IO.Path]::GetFullPath($TargetPath)
$secrets = [System.IO.Path]::GetFullPath($SecretDirectory)

if (-not (Test-Path -LiteralPath $target -PathType Container)) {
    throw "Backup target directory does not exist: $target"
}
if (-not (Test-Path -LiteralPath $secrets -PathType Container)) {
    throw "Backup secret directory does not exist: $secrets"
}
if (-not $OffHost -and -not $LocalRehearsal) {
    throw "Use -OffHost for production or -LocalRehearsal for an isolated drill target."
}
if ($OffHost -and $target.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Production backup target must be outside the repository."
}

$requiredSecrets = @(
    "backup_postgres_password",
    "backup_minio_access_key",
    "backup_minio_secret_key",
    "age_recipient.txt"
)
foreach ($name in $requiredSecrets) {
    $path = Join-Path $secrets $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -eq 0) {
        throw "Required secret file is missing or empty: $name"
    }
}

$env:BACKUP_TARGET_PATH = $target
$env:BACKUP_SECRET_DIR = $secrets
$env:BACKUP_TARGET_IS_OFFHOST = if ($OffHost) { "1" } else { "0" }
$env:ALLOW_LOCAL_BACKUP_TARGET = if ($LocalRehearsal) { "1" } else { "0" }
$env:BACKUP_PROMOTE_MONTHLY = if ($PromoteMonthly) { "1" } else { "0" }
$env:RECOVERY_POINT_ID = $RecoveryPointId

$compose = @("compose", "-f", "compose.yaml", "-f", "compose.ops.yaml")
$running = @(docker compose ps --services --filter status=running)
if ($LASTEXITCODE -ne 0) { throw "Cannot read Compose service state." }

try {
    docker compose stop proxy
    if ($LASTEXITCODE -ne 0) { throw "Cannot enter maintenance mode at proxy." }
    docker compose stop worker beat backend
    if ($LASTEXITCODE -ne 0) { throw "Cannot quiesce application writers." }

    & docker @compose --profile ops run --rm --no-deps backup-ops
    if ($LASTEXITCODE -ne 0) { throw "Encrypted recovery point creation failed." }
}
finally {
    if ($running -contains "backend") {
        docker compose up -d --wait backend
        if ($LASTEXITCODE -ne 0) { throw "Backend failed to recover after maintenance." }
    }
    if ($running -contains "worker" -or $running -contains "beat") {
        $background = @()
        if ($running -contains "worker") { $background += "worker" }
        if ($running -contains "beat") { $background += "beat" }
        docker compose up -d @background
        if ($LASTEXITCODE -ne 0) { throw "Background services failed to recover after maintenance." }
    }
    if ($running -contains "proxy") {
        docker compose up -d --wait proxy
        if ($LASTEXITCODE -ne 0) { throw "Proxy failed to recover after maintenance." }
    }
}
