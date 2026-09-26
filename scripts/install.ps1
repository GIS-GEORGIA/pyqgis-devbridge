<#
.SYNOPSIS
  One-shot bootstrap for Windows: installs the devbridge CLI, puts the
  DevBridge plugin into your QGIS profile (and enables it), and prepares
  a plugin from your QGIS profile for debugging.

.EXAMPLE
  .\scripts\install.ps1                        # pick the plugin interactively
  .\scripts\install.ps1 -Plugin selection_tools
  .\scripts\install.ps1 -Lang ka -Force
  .\scripts\install.ps1 -ProjectDir C:\src\my_plugin   # any folder instead of a profile plugin
  .\scripts\install.ps1 -SkipSetup             # only install the CLI + DevBridge plugin
#>
param(
    [string]$Plugin,          # plugin name in your QGIS profile
    [string]$ProjectDir,      # overrides -Plugin: any folder
    [string]$QgisProfile,     # QGIS profile name (default: "default")
    [string]$Lang = "en",
    [switch]$Copy,            # copy DevBridge instead of linking it
    [switch]$Force,           # replace an existing DevBridge folder in the profile
    [switch]$SkipBridge,      # don't install the DevBridge QGIS plugin
    [switch]$SkipSetup        # don't prepare a plugin (venv / debugpy / VS Code config)
)

$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent $PSScriptRoot
Set-Location $RepoDir

# Python: prefer the launcher, fall back to python on PATH
$py = $null
foreach ($cand in @(@("py", "-3"), @("python"))) {
    if (Get-Command $cand[0] -ErrorAction SilentlyContinue) { $py = $cand; break }
}
if (-not $py) { throw "Python 3.9+ not found on PATH. Install it from python.org first." }
function Invoke-Py { & $py[0] @($py[1..($py.Count)] + $args) }

# CLI in a private venv (re-runs are cheap)
$venv = Join-Path $RepoDir ".bootstrap-venv"
$venvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating .bootstrap-venv ..."
    Invoke-Py -m venv $venv
}
& $venvPy -m pip install --upgrade pip -q
& $venvPy -m pip install -e . -q
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

$devbridge = Join-Path $venv "Scripts\devbridge.exe"

if (-not $SkipBridge) {
    $bridgeArgs = @("--lang", $Lang, "install-plugin")
    if ($QgisProfile) { $bridgeArgs += @("--profile", $QgisProfile) }
    if ($Copy)  { $bridgeArgs += "--copy" }
    if ($Force) { $bridgeArgs += "--force" }
    & $devbridge @bridgeArgs
    if ($LASTEXITCODE -ne 0) { Write-Warning "DevBridge plugin install reported a problem (see above)." }
}

if (-not $SkipSetup) {
    $setupArgs = @("--lang", $Lang, "setup")
    if ($ProjectDir)      { $setupArgs += @("--project-dir", $ProjectDir) }
    elseif ($Plugin)      { $setupArgs += @("--plugin", $Plugin) }
    if ($QgisProfile)     { $setupArgs += @("--profile", $QgisProfile) }
    & $devbridge @setupArgs
    if ($LASTEXITCODE -ne 0) { throw "devbridge setup failed" }
}

Write-Host ""
Write-Host "Done. Restart QGIS, then: Plugins > DevBridge > Start debug bridge," -ForegroundColor Green
Write-Host "and in VS Code: Run and Debug > 'PyQGIS: Attach to running QGIS'." -ForegroundColor Green
