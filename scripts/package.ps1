param([string]$Compiler)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $repoRoot '.venv/Scripts/python.exe'
& $pythonPath (Join-Path $PSScriptRoot 'build.py')
if ($LASTEXITCODE -ne 0) { throw 'Application build failed' }
if (-not $Compiler) {
    $compilerPaths = @("${env:ProgramFiles(x86)}/Inno Setup 7/ISCC.exe", "${env:ProgramFiles(x86)}/Inno Setup 6/ISCC.exe", "$env:LOCALAPPDATA/Programs/Inno Setup 7/ISCC.exe")
    $Compiler = $compilerPaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $Compiler) { throw 'Install Inno Setup or pass -Compiler with the ISCC.exe path.' }
$version = (Get-Content -LiteralPath (Join-Path $repoRoot 'build/version.txt') -Raw).Trim()
& $Compiler "/DAppVersion=$version" (Join-Path $repoRoot 'installer/setup.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
$installerPath = Join-Path $repoRoot "release/CodexTaskbarCompanion-$version-Setup-x64.exe"
$digest = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$installerPath.sha256" -Value "$digest  $([System.IO.Path]::GetFileName($installerPath))" -Encoding ascii
Write-Output $installerPath
