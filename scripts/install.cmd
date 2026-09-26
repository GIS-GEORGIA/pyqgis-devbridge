@echo off
rem Double-click / cmd wrapper: runs install.ps1 without touching the
rem machine-wide PowerShell execution policy. Arguments pass through, e.g.
rem   scripts\install.cmd -Plugin selection_tools -Lang ka
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if errorlevel 1 pause
