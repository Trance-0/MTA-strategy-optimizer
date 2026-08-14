@echo off
rem
rem Start the dashboard locally on Windows.
rem
rem Reads `.env` at the repository root for the data source. Copy `sample.env`
rem to `.env` and set DATABASE=true with the PG_* values to read the PostgreSQL
rem mirror; leave DATABASE=false to read the committed CSV and JSON artifacts.
rem
rem   dashboard\run.bat          default port 8501
rem   dashboard\run.bat 8600     a different port
rem
setlocal
pushd "%~dp0.."

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8501"

where uv >nul 2>&1
if errorlevel 1 (
  echo uv is not on PATH. Install it from https://docs.astral.sh/uv/ first.
  popd
  exit /b 1
)

if not exist ".env" (
  echo No .env found. Copying sample.env, which reads the committed files.
  copy /y "sample.env" ".env" >nul
)

rem Sync only when the extra is missing, so a warm checkout starts immediately.
uv run --extra dashboard python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
  echo Installing the dashboard extra...
  uv sync --extra dashboard
)

echo Starting the dashboard on http://localhost:%PORT%
uv run --extra dashboard streamlit run dashboard/app.py --server.port %PORT%

popd
endlocal
