param(
    [string]$WorkspaceRoot = "D:\Dev\Grandakun-DCC",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repositories = @(
    "maya-mcp",
    "maya-tools-xiaota",
    "zbrush-mcp",
    "substance-painter-mcp",
    "marmoset-mcp",
    ".github",
    "dcc-mcp-catalog"
)

if (Test-Path -LiteralPath $WorkspaceRoot -PathType Leaf) {
    throw "Workspace root is not a directory: $WorkspaceRoot"
}

foreach ($name in $repositories) {
    $path = Join-Path $WorkspaceRoot $name
    $repository = "grandakun-dcc/$name"

    if (Test-Path -LiteralPath $path) {
        if (-not (Test-Path -LiteralPath (Join-Path $path ".git"))) {
            throw "Repository directory exists but is not a git repository: $path"
        }
        Write-Output "EXISTS`t$repository`t$path"
        if (-not $DryRun) {
            & git -C $path fetch --prune
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to fetch $repository. Check network access and private-repository authentication."
            }
        }
        continue
    }

    Write-Output "CLONE`t$repository`t$path"
    if (-not $DryRun) {
        New-Item -ItemType Directory -Force -Path $WorkspaceRoot | Out-Null
        & gh repo clone $repository $path
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to clone $repository. Check gh authentication and private-repository access."
        }
    }
}
