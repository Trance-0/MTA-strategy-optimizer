@echo off
rem Build and run the local two-container test stack.
rem
rem   deploy\docker\run.bat          stop the old containers, rebuild, start
rem   deploy\docker\run.bat down     stop and remove them
rem   deploy\docker\run.bat logs     follow both containers' output
rem
rem The image tag is the repository-root VERSION file, read here rather than
rem written in compose.yaml, so bumping VERSION is the only thing that rolls
rem the tag and the two cannot disagree.
rem
rem The data source is detected rather than configured here: compose.yaml
rem layers the repository root's .env over defaults.env if the file exists, and
rem falls back to the committed CSV and JSON files if it does not. This script
rem only reports which of the two happened, so a stack reading the wrong source
rem is visible at startup instead of at the first empty chart.

setlocal enabledelayedexpansion
set "HERE=%~dp0"
for /f "usebackq tokens=* delims= " %%v in ("%HERE%..\..\VERSION") do set "PROJECT_VERSION=%%v"
set "PROJECT_VERSION=%PROJECT_VERSION: =%"
set "COMPOSE=docker compose --project-directory "%HERE%." -f "%HERE%compose.yaml""

if "%~1"=="down" (
    %COMPOSE% down --remove-orphans
    goto :end
)
if "%~1"=="logs" (
    %COMPOSE% logs -f
    goto :end
)
if not "%~1"=="" if not "%~1"=="up" (
    echo usage: run.bat [up^|down^|logs] 1>&2
    exit /b 2
)

rem Down first: the previous run's containers hold the published ports, and a
rem rebuilt image does not replace a container that is already running.
%COMPOSE% down --remove-orphans
%COMPOSE% build || exit /b 1
%COMPOSE% up -d || exit /b 1

if not defined DASHBOARD_PORT set "DASHBOARD_PORT=8090"
if not defined API_PORT set "API_PORT=8501"
call :describesource
echo marketing-roi-analysis %PROJECT_VERSION%
echo   dashboard  http://localhost:%DASHBOARD_PORT%
echo   api        http://localhost:%API_PORT%/api/health
echo   data       !DATA_SOURCE!

:end
endlocal
exit /b 0

rem What the API container will actually read, resolved the same way Compose
rem resolves it: the root .env layered over defaults.env, last value winning.
rem Reported rather than acted on -- this is a description of the
rem configuration, not a second copy of it.
:describesource
set "ROOT_ENV=%HERE%..\..\.env"
set "DB_MODE="
set "PG_HOST_VALUE="
call :readkey "%HERE%defaults.env"
if exist "%ROOT_ENV%" call :readkey "%ROOT_ENV%"
if /i "!DB_MODE!"=="true" goto :describedb
if "!DB_MODE!"=="1" goto :describedb
if /i "!DB_MODE!"=="yes" goto :describedb
if /i "!DB_MODE!"=="on" goto :describedb
if exist "%ROOT_ENV%" (
  set "DATA_SOURCE=committed module files (.env sets DATABASE=false)"
) else (
  set "DATA_SOURCE=committed module files (no .env found; using defaults.env)"
)
exit /b 0
:describedb
if defined PG_HOST_VALUE (
  set "DATA_SOURCE=PostgreSQL !PG_HOST_VALUE! (from .env)"
) else (
  set "DATA_SOURCE=PostgreSQL ^<PG_HOST unset^> (from .env)"
)
exit /b 0

rem `eol=#` skips comment lines, so a commented-out DATABASE cannot be read as
rem the setting. A later file overwrites what an earlier one set, which is the
rem precedence Compose applies to the same two files.
:readkey
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%~1") do (
  set "KEY=%%a"
  set "KEY=!KEY: =!"
  if /i "!KEY!"=="DATABASE" set "DB_MODE=%%b"
  if /i "!KEY!"=="PG_HOST" set "PG_HOST_VALUE=%%b"
)
set "DB_MODE=!DB_MODE: =!"
set "PG_HOST_VALUE=!PG_HOST_VALUE: =!"
exit /b 0
