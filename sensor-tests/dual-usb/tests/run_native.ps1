$ErrorActionPreference='Stop'
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$installation=& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $installation) { throw 'Visual Studio C++ Build Tools not found' }
$vcvars=Join-Path $installation 'VC\Auxiliary\Build\vcvars64.bat'
$root=Split-Path -Parent $PSScriptRoot
$out=Join-Path $root '.pio\native-test'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$source=Join-Path $PSScriptRoot 'telemetry_sim.cpp'
$include=Join-Path $root 'include'
$exe=Join-Path $out 'telemetry_sim.exe'
$command='call "'+$vcvars+'" >nul && cl /nologo /EHsc /std:c++17 /W4 /I"'+$include+'" "'+$source+'" /Fe:"'+$exe+'" /Fo:"'+(Join-Path $out 'telemetry_sim.obj')+'" && "'+$exe+'"'
cmd.exe /d /c $command
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
