param(
    [Parameter(Mandatory = $true)][string]$TargetPath,
    [Parameter(Mandatory = $true)][string]$SecretDirectory,
    [Parameter(Mandatory = $true)][string]$ArchivePath,
    [string]$BackendImage = "podoria-crm-backend"
)

$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetPath)
$secrets = [System.IO.Path]::GetFullPath($SecretDirectory)
$archive = [System.IO.Path]::GetFullPath($ArchivePath)

if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
    throw "Recovery archive does not exist: $archive"
}
if (-not $archive.StartsWith($target, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Recovery archive must be inside the validated backup target."
}
$archiveName = [System.IO.Path]::GetFileName($archive)
if ($archiveName -notmatch '^podoria-(\d{8}T\d{6}Z)\.tar\.gz\.age$') {
    throw "Invalid recovery archive name."
}
$recoveryPoint = $Matches[1]
$relative = [System.IO.Path]::GetRelativePath($target, $archive).Replace('\', '/')

foreach ($name in @("restore_postgres_password", "restore_minio_access_key", "restore_minio_secret_key", "age_identity.txt")) {
    $path = Join-Path $secrets $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -eq 0) {
        throw "Required restore secret file is missing or empty: $name"
    }
}

$env:BACKUP_TARGET_PATH = $target
$env:BACKUP_SECRET_DIR = $secrets
$env:RECOVERY_POINT_FILE = "/backups/$relative"
$env:RESTORE_CONFIRM = "restore:$recoveryPoint"
$env:RESTORE_BACKEND_IMAGE = $BackendImage
$compose = @("compose", "-f", "compose.yaml", "-f", "compose.ops.yaml", "--profile", "ops")

try {
    & docker @compose up -d --wait restore-postgres restore-minio
    if ($LASTEXITCODE -ne 0) { throw "Isolated restore dependencies failed to start." }
    & docker @compose run --rm restore-minio-init
    if ($LASTEXITCODE -ne 0) { throw "Isolated restore bucket initialization failed." }
    & docker @compose run --rm --no-deps restore-ops
    if ($LASTEXITCODE -ne 0) { throw "Recovery point restore failed." }
    & docker @compose run --rm --no-deps restore-backend-check
    if ($LASTEXITCODE -ne 0) { throw "Restored application integrity verification failed." }
}
finally {
    & docker @compose rm -sf restore-postgres restore-minio restore-minio-init | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Exact restore-drill container cleanup failed." }
}
