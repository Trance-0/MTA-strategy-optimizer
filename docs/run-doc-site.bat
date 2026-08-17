@echo off
setlocal EnableExtensions

rem On success the dev/preview server holds the window open by itself, and a
rem `build` run ends the script normally. On failure nothing does, and a
rem window opened by an Explorer double-click closes instantly, taking the
rem diagnosis with it -- so every failure path below ends in `pause`. Set
rem DOCS_NONINTERACTIVE=1 to suppress it when scripting this.

set "SCRIPT_DIRECTORY=%~dp0"
pushd "%SCRIPT_DIRECTORY%" >nul
if errorlevel 1 (
  echo [docs] ERROR: could not change to %SCRIPT_DIRECTORY%.
  goto :fail
)

set "RUN_MODE=dev"
if /i "%~1"=="build" set "RUN_MODE=build"
if /i "%~1"=="preview" set "RUN_MODE=preview"
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-h" goto :help

where node >nul 2>&1
if errorlevel 1 (
  echo [docs] ERROR: Node.js is not available on PATH.
  popd
  goto :fail
)
where npm >nul 2>&1
if errorlevel 1 (
  echo [docs] ERROR: npm is not available on PATH.
  popd
  goto :fail
)

echo [docs] Directory: %CD%
echo [docs] Mode: %RUN_MODE%
node --version
call npm --version

if not exist "node_modules\vitepress\package.json" (
  if exist "package-lock.json" (call npm ci) else (call npm install)
  if errorlevel 1 (
    echo [docs] ERROR: dependency installation failed.
    popd
    goto :fail
  )
)

call npm run %RUN_MODE%
set "EXIT_STATUS=%ERRORLEVEL%"
popd
rem Ctrl+C on the dev/preview server is a stop the reader asked for, and cmd
rem reports it as 130 or as 0; neither is a failure worth holding the window
rem open for.
if not "%EXIT_STATUS%"=="0" if not "%EXIT_STATUS%"=="130" goto :fail
exit /b %EXIT_STATUS%

:fail
if not defined DOCS_NONINTERACTIVE pause
exit /b 1

:help
echo Usage: run-doc-site.bat [dev^|build^|preview]
popd
exit /b 0
