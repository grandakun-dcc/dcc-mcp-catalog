param(
    [string]$WorkspaceRoot,
    [string]$Python = "python",
    [switch]$SkipInstalledExtensions
)

$ErrorActionPreference = "Stop"
$catalogRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Split-Path -Parent $catalogRoot
}
$validator = Join-Path $PSScriptRoot "validate_catalog.py"
$servers = Join-Path $catalogRoot "catalog\servers.yaml"
$compatibility = Join-Path $catalogRoot "catalog\compatibility.yaml"
$releases = Join-Path $catalogRoot "catalog\releases.lock.yaml"
$failed = $false
$canValidate = $true

function Test-GitRepository {
    param([string]$Path)

    try {
        $inside = (& git -C $Path rev-parse --is-inside-work-tree 2>$null)
        return $LASTEXITCODE -eq 0 -and (($inside -join "").Trim() -eq "true")
    }
    catch {
        return $false
    }
}

$rows = & $Python $validator $servers --compatibility $compatibility --releases $releases --list-repositories
if ($LASTEXITCODE -ne 0) {
    Write-Output "INVALID_CATALOG"
    exit 1
}

foreach ($row in $rows) {
    $parts = $row -split "`t", 3
    $repository = $parts[0]
    $name = $parts[1]
    $lockedCommit = $parts[2]
    $path = Join-Path $WorkspaceRoot $name
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        Write-Output "MISSING`t$repository`t$path"
        $failed = $true
        $canValidate = $false
        continue
    }
    if (-not (Test-GitRepository -Path $path)) {
        Write-Output "NOT_GIT`t$repository`t$path"
        $failed = $true
        $canValidate = $false
        continue
    }

    $branch = (& git -C $path branch --show-current).Trim()
    $dirty = [bool](& git -C $path status --porcelain)
    $remote = (& git -C $path remote get-url origin).Trim()
    $currentCommit = (& git -C $path rev-parse HEAD).Trim()
    $state = if ($dirty) { "DIRTY" } else { "CLEAN" }
    Write-Output "$state`t$repository`t$branch`t$currentCommit`t$lockedCommit`t$remote"
    if ($dirty) {
        $failed = $true
    }
}

if ($canValidate) {
    $arguments = @(
        $validator,
        $servers,
        "--compatibility", $compatibility,
        "--releases", $releases,
        "--workspace-root", $WorkspaceRoot
    )
    if (-not $SkipInstalledExtensions) {
        $arguments += "--check-installed"
    }
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) {
        $failed = $true
    }
}

if ($failed) {
    exit 1
}
exit 0
