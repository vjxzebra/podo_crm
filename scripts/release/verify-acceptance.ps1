param(
    [string]$ManifestPath = "docs/evidence/tp-904/acceptance-gate.json"
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))
$manifestFullPath = if ([System.IO.Path]::IsPathRooted($ManifestPath)) {
    [System.IO.Path]::GetFullPath($ManifestPath)
}
else {
    [System.IO.Path]::GetFullPath((Join-Path $repoRoot $ManifestPath))
}

function Assert-Gate([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

Assert-Gate ($manifestFullPath.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) `
    "Acceptance manifest must remain inside the repository."
Assert-Gate (Test-Path -LiteralPath $manifestFullPath -PathType Leaf) `
    "Acceptance manifest does not exist: $manifestFullPath"

$manifest = Get-Content -LiteralPath $manifestFullPath -Raw | ConvertFrom-Json
$expectedIds = 1..23 | ForEach-Object { "AC-{0:D2}" -f $_ }
$entries = @($manifest.acceptance)
$actualIds = @($entries | ForEach-Object { $_.id })

Assert-Gate ($manifest.packet -eq "TP-904") "Unexpected packet in acceptance manifest."
Assert-Gate ($manifest.result -eq "verified") "TP-904 result is not verified."
Assert-Gate ($entries.Count -eq 23) "Acceptance manifest must contain exactly 23 entries."
Assert-Gate ((@($actualIds | Sort-Object -Unique)).Count -eq 23) `
    "Acceptance manifest contains duplicate IDs."
Assert-Gate ((Compare-Object $expectedIds ($actualIds | Sort-Object)).Count -eq 0) `
    "Acceptance manifest has missing or unexpected IDs."
Assert-Gate (@($entries | Where-Object { $_.status -ne "verified" }).Count -eq 0) `
    "Every acceptance entry must be verified."
Assert-Gate ($manifest.summary.criteria_total -eq 23) "Summary criterion total is not 23."
Assert-Gate ($manifest.summary.criteria_verified -eq 23) "Summary verified total is not 23."
Assert-Gate ($manifest.summary.roles -eq 3 -and $manifest.summary.viewports -eq 3) `
    "Summary role/viewport total is invalid."

foreach ($entry in $entries) {
    Assert-Gate (-not [string]::IsNullOrWhiteSpace($entry.criterion)) `
        "$($entry.id) has no criterion text."
    $paths = @($entry.evidence)
    Assert-Gate ($paths.Count -gt 0) "$($entry.id) has no evidence paths."
    foreach ($path in $paths) {
        $fullPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $path))
        Assert-Gate ($fullPath.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) `
            "$($entry.id) evidence escapes the repository: $path"
        Assert-Gate (Test-Path -LiteralPath $fullPath) `
            "$($entry.id) evidence does not exist: $path"
    }
}

$gates = $manifest.release_gates
Assert-Gate (
    $gates.canonical.backend_tests -eq 364 -and
    $gates.canonical.frontend_tests -eq 198 -and
    $gates.canonical.component_axe_scenarios -eq 40 -and
    $gates.canonical.ruff_files -eq 246 -and
    $gates.canonical.mypy_source_files -eq 188 -and
    $gates.canonical.openapi_snapshot_current -and
    $gates.canonical.production_build
) "Canonical quality summary is incomplete."
Assert-Gate (
    $gates.database.migration_count -eq 53 -and
    $gates.database.pending_migrations -eq 0 -and
    $gates.database.invalid_constraints -eq 0 -and
    $gates.database.object_reference_count -eq 10 -and
    $gates.database.missing_objects -eq 0
) "Database/restore gate is incomplete."
Assert-Gate (
    $gates.dependency_audit.npm_known_vulnerabilities -eq 0 -and
    $gates.dependency_audit.python_dependencies_audited -eq 43 -and
    $gates.dependency_audit.python_known_vulnerabilities -eq 0
) "Dependency audit gate is incomplete."
Assert-Gate (
    $gates.runtime_images.backend_critical_or_high -eq 0 -and
    $gates.runtime_images.web_critical_or_high -eq 0 -and
    $gates.runtime_images.ops_critical_or_high -eq 0
) "Runtime image vulnerability gate is incomplete."
Assert-Gate (
    $gates.runtime_images.backend_image -match '^sha256:[0-9a-f]{64}$' -and
    $gates.runtime_images.web_image -match '^sha256:[0-9a-f]{64}$'
) "Candidate images are not immutable IDs."
Assert-Gate (
    $gates.production_rehearsal.recovery_manifest_preflight -and
    $gates.production_rehearsal.deploy_check_completed -and
    $gates.production_rehearsal.migration_count -eq 53 -and
    $gates.production_rehearsal.root_status -eq 200 -and
    $gates.production_rehearsal.readiness_status -eq 200 -and
    $gates.production_rehearsal.unauthenticated_session_status -eq 401 -and
    $gates.production_rehearsal.application_source_mounts -eq 0 -and
    $gates.production_rehearsal.candidate_service_count -eq 8 -and
    $gates.production_rehearsal.file_mounted_secrets
) "Production rehearsal gate is incomplete."
Assert-Gate (
    $gates.cleanup.uat_users -eq 0 -and
    $gates.cleanup.uat_patients -eq 0 -and
    $gates.cleanup.uat_appointments -eq 0 -and
    $gates.cleanup.release_containers -eq 0 -and
    $gates.cleanup.release_volumes -eq 0 -and
    $gates.cleanup.release_networks -eq 0 -and
    $gates.cleanup.temporary_secret_directories -eq 0
) "Fixture/rehearsal cleanup gate is incomplete."

$browserPath = Join-Path $repoRoot $gates.browser.evidence
$browser = Get-Content -LiteralPath $browserPath -Raw | ConvertFrom-Json
Assert-Gate (
    $browser.summary.roles -eq 3 -and
    $browser.summary.viewports -eq 3 -and
    $browser.summary.route_checks -eq 75 -and
    $browser.summary.forbidden_redirect_checks -eq 11 -and
    $browser.summary.serious_or_critical_axe_violations -eq 0 -and
    $browser.summary.browser_warnings_or_errors -eq 0
) "Browser evidence summary is not the required 3-role/3-viewport result."

$operationsPath = Join-Path $repoRoot $gates.tp903_operations.evidence
$operations = Get-Content -LiteralPath $operationsPath -Raw | ConvertFrom-Json
Assert-Gate (
    $operations.backup.encrypted -and
    -not $operations.backup.plaintext_stage_retained -and
    $operations.negative_restore_gates.invalid_confirmation_rejected -and
    $operations.negative_restore_gates.corrupt_ciphertext_rejected_before_target_connection -and
    $operations.isolated_restore.missing_objects -eq 0 -and
    $operations.isolated_restore.pending_migrations -eq 0 -and
    $operations.isolated_restore.invalid_constraints -eq 0 -and
    $operations.deployment.root_status -eq 200 -and
    $operations.deployment.readiness_status -eq 200 -and
    $operations.deployment.unauthenticated_session_status -eq 401 -and
    $operations.rollback.root_status -eq 200 -and
    $operations.rollback.readiness_status -eq 200 -and
    $operations.rollback.unauthenticated_session_status -eq 401 -and
    $operations.rollback.reverse_migrations_run -eq $false
) "TP-903 restore/deployment/rollback evidence is not green."

$matrixPath = Join-Path $repoRoot "docs/requirements/traceability-matrix.md"
$matrixLines = Get-Content -LiteralPath $matrixPath
foreach ($id in $expectedIds) {
    $rows = @($matrixLines | Where-Object { $_ -match "^\| $id \|" })
    Assert-Gate ($rows.Count -eq 1) "Traceability matrix must contain exactly one $id row."
    Assert-Gate ($rows[0].Contains('`verified`')) "$id is not verified in traceability matrix."
}

[pscustomobject]@{
    packet = "TP-904"
    status = "verified"
    criteria = 23
    roles = 3
    viewports = 3
    route_checks = 75
    forbidden_redirect_checks = 11
} | ConvertTo-Json -Compress
