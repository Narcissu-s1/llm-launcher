@echo off
setlocal
cd /d "%~dp0"
set "UV=uv"
where uv >nul 2>nul
if errorlevel 1 (
  set "UV=%USERPROFILE%\.local\bin\uv.exe"
  if not exist "%USERPROFILE%\.local\bin\uv.exe" (
    echo uv is not installed. See README.md for setup instructions.
    pause
    exit /b 1
  )
)
"%UV%" run --locked --group build python scripts/build.py %*
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
