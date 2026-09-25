# One-shot bootstrap for Windows PowerShell.
param(
    [string]$ProjectDir = (Get-Location),
    [string]$Lang = "en"
)

$ScriptDir = Split-Path -Parent $PSScriptRoot
Set-Location $ScriptDir

python -m venv .bootstrap-venv
& .\.bootstrap-venv\Scripts\Activate.ps1
pip install --upgrade pip -q
pip install -e . -q

devbridge setup --project-dir $ProjectDir --lang $Lang
