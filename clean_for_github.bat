@echo off
setlocal

cd /d "%~dp0"

echo Cleaning local runtime artifacts...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root=(Resolve-Path '.').Path; $targets=@('output\tmp','output\logs'); foreach($rel in $targets){ $path=Join-Path $root $rel; if(Test-Path -LiteralPath $path){ Get-ChildItem -LiteralPath $path -Force | Remove-Item -Recurse -Force } }; Get-ChildItem -Path $root -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force"

echo.
echo Done. Review with:
echo   git status --short
echo   git diff --check
echo.
pause
