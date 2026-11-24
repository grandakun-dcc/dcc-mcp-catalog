param(
    [string]$WorkspaceRoot = "D:\Dev\Grandakun-DCC"
)

$repositories = @(
    "maya-mcp",
    "maya-tools-xiaota",
    "zbrush-mcp",
    "substance-painter-mcp",
    "marmoset-mcp",
    ".github",
    "dcc-mcp-catalog"
)
$failed = $false

foreach ($name in $repositories) {
    $path = Join-Path $WorkspaceRoot $name
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        Write-Output "MISSING`t$name`t$path"
        $failed = $true
        continue
    }
    if (-not (Test-Path -LiteralPath (Join-Path $path ".git"))) {
        Write-Output "NOT_GIT`t$name`t$path"
        $failed = $true
        continue
    }

    $branch = (& git -C $path branch --show-current).Trim()
    $dirty = [bool](& git -C $path status --porcelain)
    $remote = (& git -C $path remote get-url origin).Trim()
    $state = if ($dirty) { "DIRTY" } else { "CLEAN" }
    Write-Output "$state`t$name`t$branch`t$remote"
}

if ($failed) {
    exit 1
}
exit 0
