[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it from https://docs.astral.sh/uv/"
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js and npm are required."
}

& uv sync
if (-not (Test-Path -LiteralPath (Join-Path $Root "app\web\node_modules"))) {
    & npm.cmd --prefix (Join-Path $Root "app\web") ci
}

function Start-Terminal {
    param([string]$Title, [string]$WorkingDirectory, [string]$Command)
    $safeTitle = $Title.Replace("'", "''")
    $safeDirectory = $WorkingDirectory.Replace("'", "''")
    $script = "`$Host.UI.RawUI.WindowTitle = '$safeTitle'; Set-Location -LiteralPath '$safeDirectory'; $Command"
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $script
    )
}

$apiCommand = "`$env:DATABASE_URL = 'sqlite+pysqlite:///var/showcase.db'; `$env:STORAGE_DIR = 'var/documents'; uv run python -m app.cli reset; uv run uvicorn app.api.main:app --host 127.0.0.1 --port 8106"
$webDirectory = Join-Path $Root "app\web"
Start-Terminal "Proposal API" $Root $apiCommand
Start-Terminal "Proposal Web" $webDirectory "npm.cmd run dev -- --hostname 127.0.0.1 --port 3106"

Write-Host "Proposal demo starting at http://127.0.0.1:3106"
Write-Host "API health: http://127.0.0.1:8106/health"
