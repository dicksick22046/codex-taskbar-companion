$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv/Scripts/pythonw.exe'
$entry = Join-Path $PSScriptRoot 'app.py'
if (-not (Test-Path -LiteralPath $python)) {
    throw '请先按 README 创建 .venv 并安装依赖。'
}
Start-Process -FilePath $python -ArgumentList ('"' + $entry + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
