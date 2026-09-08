$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $repoRoot '.venv/Scripts/pythonw.exe'
$previewPath = Join-Path $PSScriptRoot 'preview_session.py'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw '请先按 README 安装开发环境。' }
Start-Process -FilePath $pythonPath -ArgumentList ('"' + $previewPath + '"') -WorkingDirectory $repoRoot -WindowStyle Hidden
