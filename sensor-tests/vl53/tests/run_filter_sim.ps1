$ErrorActionPreference = 'Stop'

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $vswhere)) {
    throw 'Visual Studio Build Tools (vswhere.exe) not found.'
}
$installation = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $installation) {
    throw 'Visual Studio C++ Build Tools not found.'
}
$vcvars = Join-Path $installation 'VC\Auxiliary\Build\vcvars64.bat'
$root = Split-Path -Parent $PSScriptRoot
$output = Join-Path $root '.pio\native-filter'
New-Item -ItemType Directory -Force -Path $output | Out-Null
$source = Join-Path $PSScriptRoot 'filter_sim.cpp'
$include = Join-Path $root 'include'
$exe = Join-Path $output 'filter_sim.exe'

$command = 'call "' + $vcvars + '" >nul && cl /nologo /EHsc /std:c++17 /W4 /I"' + $include + '" "' + $source + '" /Fe:"' + $exe + '" /Fo:"' + (Join-Path $output 'filter_sim.obj') + '" && "' + $exe + '"'
cmd.exe /d /c $command
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
