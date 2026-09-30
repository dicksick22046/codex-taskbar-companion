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
$releasePath = Split-Path $installerPath -Parent
New-Item -ItemType Directory -Path $releasePath -Force | Out-Null
$frameworkPath = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319'
$bootstrapSource = Join-Path $repoRoot 'installer/Bootstrap.cs'
$payloadPath = Join-Path $repoRoot 'build/setup-payload.exe'
$manifestPath = Join-Path $repoRoot 'installer/bootstrap.manifest'
$iconPath = Join-Path $repoRoot 'build/app.ico'
$versionSource = Join-Path $repoRoot 'build/bootstrap-version.cs'
Set-Content -LiteralPath $versionSource -Encoding utf8 -Value "[assembly: System.Reflection.AssemblyVersion(`"$version.0`")]`n[assembly: System.Reflection.AssemblyProduct(`"Codex Taskbar Companion`")]`n[assembly: System.Reflection.AssemblyTitle(`"Codex Taskbar Companion Setup`")]"
& (Join-Path $frameworkPath 'csc.exe') /nologo /target:winexe /platform:x64 /r:System.Management.dll /r:System.Windows.Forms.dll /r:Microsoft.CSharp.dll "/win32manifest:$manifestPath" "/win32icon:$iconPath" "/resource:$payloadPath,InnoSetup" "/out:$installerPath" $versionSource $bootstrapSource
if ($LASTEXITCODE -ne 0) { throw 'Installer bootstrap build failed' }
$digest = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$installerPath.sha256" -Value "$digest  $([System.IO.Path]::GetFileName($installerPath))" -Encoding ascii
Write-Output $installerPath
