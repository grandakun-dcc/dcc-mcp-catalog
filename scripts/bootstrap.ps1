param(
    [string]$WorkspaceRoot = "D:\Dev\Grandakun-DCC",
    [string]$Python = "python",
    [switch]$InstallExtensions,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$catalogRoot = Split-Path -Parent $PSScriptRoot
$validator = Join-Path $PSScriptRoot "validate_catalog.py"
$servers = Join-Path $catalogRoot "catalog\servers.yaml"
$compatibility = Join-Path $catalogRoot "catalog\compatibility.yaml"
$releases = Join-Path $catalogRoot "catalog\releases.lock.yaml"

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

if (Test-Path -LiteralPath $WorkspaceRoot -PathType Leaf) {
    throw "Workspace root is not a directory: $WorkspaceRoot"
}

$rows = & $Python $validator $servers --compatibility $compatibility --releases $releases --list-repositories
if ($LASTEXITCODE -ne 0) {
    throw "Catalog validation failed"
}

foreach ($row in $rows) {
    $parts = $row -split "`t", 2
    $repository = $parts[0]
    $name = $parts[1]
    $path = Join-Path $WorkspaceRoot $name

    if (Test-Path -LiteralPath $path) {
        if (-not (Test-GitRepository -Path $path)) {
            throw "Repository directory exists but is not a git repository: $path"
        }
        Write-Output "EXISTS`t$repository`t$path"
        if (-not $DryRun) {
            & git -C $path fetch --prune
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to fetch $repository"
            }
        }
        continue
    }

    Write-Output "CLONE`t$repository`t$path"
    if (-not $DryRun) {
        New-Item -ItemType Directory -Force -Path $WorkspaceRoot | Out-Null
        & gh repo clone $repository $path
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to clone $repository"
        }
    }
}

if ($InstallExtensions) {
    $packages = @(
        (Join-Path $WorkspaceRoot "maya-mcp"),
        (Join-Path $WorkspaceRoot "maya-tools-xiaota\integrations\mcp"),
        (Join-Path $WorkspaceRoot "maya-tools-hairpin\integrations\mcp"),
        (Join-Path $WorkspaceRoot "maya-tools-openai-gen-maya\integrations\mcp")
    )
    foreach ($package in $packages) {
        Write-Output "INSTALL`t$package"
        if (-not $DryRun) {
            & $Python -m pip install -e $package
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to install $package"
            }
        }
    }
}
