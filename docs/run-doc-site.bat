@echo off
setlocal EnableExtensions

set "SCRIPT_DIRECTORY=%~dp0"
pushd "%SCRIPT_DIRECTORY%" >nul
if errorlevel 1 exit /b 1

set "RUN_MODE=dev"
if /i "%~1"=="build" set "RUN_MODE=build"
if /i "%~1"=="preview" set "RUN_MODE=preview"
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-h" goto :help

where node >nul 2>&1
if errorlevel 1 (
  echo [docs] ERROR: Node.js is not available on PATH.
  popd
  exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
  echo [docs] ERROR: npm is not available on PATH.
  popd
  exit /b 1
)

echo [docs] Directory: %CD%
echo [docs] Mode: %RUN_MODE%
node --version
call npm --version

if not exist "node_modules\vitepress\package.json" (
  if exist "package-lock.json" (call npm ci) else (call npm install)
  if errorlevel 1 (
    popd
    exit /b 1
  )
)

call npm run %RUN_MODE%
set "EXIT_STATUS=%ERRORLEVEL%"
popd
exit /b %EXIT_STATUS%

:help
echo Usage: run-doc-site.bat [dev^|build^|preview]
popd
exit /b 0
