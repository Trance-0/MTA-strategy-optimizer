@echo off
rem
rem Start the dashboard locally on Windows.
rem
rem One click from a clean clone: this checks the toolchain, installs the
rem dependencies, builds the client, and starts Flask to serve both the JSON
rem API and that client. Node.js and uv must be installed; failures name the
rem missing tool before changing the checkout.
rem
rem Reads `.env` at the repository root for the data source. Copy `sample.env`
rem to `.env` and set DATABASE=true with the PG_* values to read the PostgreSQL
rem mirror; leave DATABASE=false to read the committed CSV and JSON artifacts.
rem Nothing about this command changes between the two.
rem
rem   dashboard\run.bat              default port 8501, opens a browser
rem   dashboard\run.bat 8600         a different port
rem   dashboard\run.bat --no-open    do not open a browser
rem   dashboard\run.bat --rebuild    discard and rebuild the client
rem
rem Every failure prints what went wrong, what to do about it, and what to
rem include in a bug report. `--rebuild` is the first thing to try when the
rem page loads but looks wrong.
rem
setlocal enabledelayedexpansion

rem Vite's own engine range, `^20.19.0 || >=22.12.0`, as one comparable integer
rem per boundary: major * 1000000 + minor * 1000 + patch. The requirement is not
rem a round major number, and rounding it down to one is what the check below
rem exists to avoid -- see the failure it reports.
set "REQUIRED_NODE_TEXT=20.19.0 or newer in the 20 series, or 22.12.0 or newer"
set "NODE_20_FLOOR=20019000"
set "NODE_21_FLOOR=21000000"
set "NODE_22_FLOOR=22012000"
set "ISSUES_URL=https://github.com/Trance-0/MTA-strategy-optimizer/issues"

set "DASHBOARD_DIR=%~dp0"
rem Strip the trailing backslash, so paths built below do not double it.
if "%DASHBOARD_DIR:~-1%"=="\" set "DASHBOARD_DIR=%DASHBOARD_DIR:~0,-1%"
set "LOG_FILE=%DASHBOARD_DIR%\.run.log"

set "PORT=8501"
set "OPEN_BROWSER=1"
set "REBUILD=0"
set "FAILED_STEP=startup"

rem On success the server holds the window open by itself. On failure nothing
rem does, and a window opened by an Explorer double-click closes instantly,
rem taking the diagnosis with it -- so the failure path ends in `pause`. Set
rem DASHBOARD_NONINTERACTIVE=1 to suppress it when scripting this.

:parse
if "%~1"=="" goto parsed
if /i "%~1"=="--no-open" (
  set "OPEN_BROWSER=0"
) else if /i "%~1"=="--rebuild" (
  set "REBUILD=1"
) else if /i "%~1"=="-h" (
  goto usage
) else if /i "%~1"=="--help" (
  goto usage
) else (
  rem Anything left must be the port. Reject non-numeric input here rather
  rem than letting it reach the server as a silently ignored argument.
  rem
  rem The rejection is a `goto` to a label rather than an `exit /b 2` written
  rem here, because an `exit /b` inside a `for` inside this parenthesised block
  rem prints its message and then returns 0 to the caller: the code is lost on
  rem the way out of the nesting, which makes a typo in a script that invokes
  rem this one look like a successful start.
  set "CANDIDATE=%~1"
  set "BAD_ARGUMENT="
  for /f "delims=0123456789" %%c in ("!CANDIDATE!") do set "BAD_ARGUMENT=1"
  if defined BAD_ARGUMENT goto badargument
  set "PORT=%~1"
)
shift
goto parse

rem The redirection is written before the `echo` rather than after it: a
rem trailing `1>&2` is separated from the text by a space that cmd includes in
rem the output.
:badargument
>&2 echo Unrecognised argument: !CANDIDATE!
>&2 echo Usage: run.bat [port] [--no-open] [--rebuild]
exit /b 2

rem The banner at the top of this file, reprinted: every line from the second
rem until the first that is not a comment, which is the `setlocal` closing the
rem block. One text, so the help and the file being read cannot disagree.
:usage
set "FIRST=1"
for /f "usebackq delims=" %%l in ("%~f0") do (
  if defined FIRST (
    set "FIRST="
  ) else (
    set "LINE=%%l"
    if /i "!LINE:~0,3!"=="rem" (echo(!LINE:~4!) else (goto usagedone)
  )
)
:usagedone
exit /b 0

:parsed
if %PORT% LSS 1 goto badport
if %PORT% GTR 65535 goto badport
goto begin

:badport
>&2 echo Port must be between 1 and 65535; got %PORT%.
exit /b 2

:begin
pushd "%DASHBOARD_DIR%\.."
set "REPO_ROOT=%CD%"

rem ---------------------------------------------------------------------------
rem 1. Toolchain
rem ---------------------------------------------------------------------------

echo.
echo [1/4] Checking the toolchain

set "FAILED_STEP=Node.js is not installed"
where node >nul 2>&1
if errorlevel 1 (
  call :banner "Node.js is not installed"
  echo   The dashboard is a Node application and cannot start without it.
  echo.
  echo     Download the Long Term Support installer from:
  echo         https://nodejs.org/
  echo.
  echo     Or with a package manager:
  echo         winget install OpenJS.NodeJS.LTS
  echo.
  echo   After installing, CLOSE THIS WINDOW and open a new one before
  echo   running this again -- an installer updates PATH only for windows
  echo   opened after it finishes.
  goto report
)

rem `node -p` rather than parsing `node -v`, so a prerelease suffix such as
rem v23.0.0-nightly cannot break the comparison.
set "NODE_ENCODED="
for /f "delims=" %%v in ('node -p "const [a,b,c] = process.versions.node.split('.').map(Number); a * 1000000 + b * 1000 + c" 2^>nul') do set "NODE_ENCODED=%%v"
set "FAILED_STEP=Node.js is too old"
if not defined NODE_ENCODED (
  call :banner "Node.js could not be run"
  echo   node is on PATH but did not report a version. The installation may
  echo   be damaged, or blocked by a security policy.
  echo.
  echo     Try:  node -v
  echo.
  echo   Reinstall from https://nodejs.org/ if that fails too.
  goto report
)

rem The minor version matters, and checking only the major is the bug this
rem replaced: Vite's native bundler binding is an *optional* dependency
rem carrying the same engine range, so on 22.11 npm quietly skips it, reports a
rem successful install, and the build then dies with "Cannot find module
rem './rolldown-binding...node'" -- a message that names neither Node nor the
rem version. Failing here names both.
set "NODE_OK=0"
if %NODE_ENCODED% GEQ %NODE_22_FLOOR% set "NODE_OK=1"
if %NODE_ENCODED% GEQ %NODE_20_FLOOR% if %NODE_ENCODED% LSS %NODE_21_FLOOR% set "NODE_OK=1"
if "%NODE_OK%"=="0" (
  call :banner "Node.js %REQUIRED_NODE_TEXT% is required"
  for /f "delims=" %%v in ('node -v') do echo   Found: %%v
  echo.
  echo     This is Vite's own engine range. Its bundler ships as a
  echo     platform-specific binary that npm installs only when the running
  echo     Node satisfies that range, and skips silently otherwise -- so an
  echo     unsupported version installs cleanly and fails at build time with a
  echo     missing-module error naming neither cause.
  echo.
  echo     Upgrade from https://nodejs.org/, or with a version manager:
  echo         nvm install 22 ^&^& nvm use 22
  echo         fnm install 22 ^&^& fnm use 22
  goto report
)

set "FAILED_STEP=npm is not installed"
where npm >nul 2>&1
if errorlevel 1 (
  call :banner "npm is not installed"
  echo   Node.js is present but npm is not on PATH.
  echo.
  echo   npm ships with the official Node.js installer, so this usually means
  echo   a partial installation. Reinstall from https://nodejs.org/.
  goto report
)

for /f "delims=" %%v in ('node -v') do set "NODE_VERSION=%%v"
for /f "delims=" %%v in ('npm -v') do set "NPM_VERSION=%%v"
echo         node %NODE_VERSION%, npm %NPM_VERSION%

set "FAILED_STEP=uv is not installed"
where uv >nul 2>&1
if errorlevel 1 (
  call :banner "uv is not installed"
  echo   The Flask backend uses the repository's locked Python environment.
  echo   Install uv from:
  echo       https://docs.astral.sh/uv/getting-started/installation/
  goto report
)
for /f "delims=" %%v in ('uv --version') do echo         %%v

rem ---------------------------------------------------------------------------
rem 2. Configuration
rem ---------------------------------------------------------------------------

echo.
echo [2/4] Checking the configuration

set "FAILED_STEP=configuration"
if not exist ".env" (
  if not exist "sample.env" (
    call :banner "Neither .env nor sample.env exists"
    echo   The repository is incomplete: sample.env is tracked and should be
    echo   here.
    echo.
    echo     Re-clone the repository, or restore the file:
    echo         git checkout sample.env
    goto report
  )
  copy /y "sample.env" ".env" >nul 2>&1
  if errorlevel 1 (
    call :banner "Could not create .env"
    echo   Copying sample.env to .env failed, usually because this folder is
    echo   not writable by the current user, or is synchronised by a client
    echo   holding the file open.
    echo.
    echo     Check the folder's permissions, or create the file by hand:
    echo         copy sample.env .env
    goto report
  )
  echo         Created .env from sample.env -- reads the committed files.
) else (
  echo         .env found.
)

rem ---------------------------------------------------------------------------
rem 3. Dependencies
rem ---------------------------------------------------------------------------

echo.
echo [3/4] Checking the dependencies

rem `vite` standing in for the client tree: an interrupted install leaves
rem node_modules present but incomplete, and testing only for the directory
rem would then skip the repair.
set "FAILED_STEP=dependency installation"
set "NEEDS_INSTALL=0"
if not exist "%DASHBOARD_DIR%\node_modules" set "NEEDS_INSTALL=1"
if not exist "%DASHBOARD_DIR%\node_modules\vite" set "NEEDS_INSTALL=1"

rem npm is run from the dashboard directory rather than pointed at it with
rem `--prefix`, because `--prefix` sets where `node_modules` is written but not
rem where the manifest is read from: the npm 10 that ships with Node 20 and 22
rem still reads package.json from the working directory, so a fresh clone fails
rem with ENOENT naming the repository root.
if "%NEEDS_INSTALL%"=="1" (
  echo         Installing ^(a few minutes on the first run^)...
  pushd "%DASHBOARD_DIR%"
  call npm install --no-audit --no-fund >"%LOG_FILE%" 2>&1
  set "NPM_STATUS=!ERRORLEVEL!"
  popd
  if not "!NPM_STATUS!"=="0" (
    call :banner "Dependency installation failed"
    echo   npm install did not complete. The most common causes:
    echo.
    echo     * No network access, or a proxy or firewall blocking the
    echo       registry.  Test it:  npm ping
    echo.
    echo     * A corporate registry needing configuration.
    echo       Check it:  npm config get registry
    echo.
    echo     * A partly written node_modules from an interrupted run.
    echo       Clear it:  rmdir /s /q dashboard\node_modules
    goto report
  )
  echo         Installed.
) else (
  echo         Already installed.
)

set "FAILED_STEP=backend dependency installation"
uv sync --extra backend >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
  call :banner "Backend dependency installation failed"
  echo   uv could not install the locked Flask backend environment.
  echo   Run this command for the complete diagnostic:
  echo       uv sync --extra backend
  goto report
)
echo         Backend dependencies ready.

rem ---------------------------------------------------------------------------
rem 4. Client build
rem ---------------------------------------------------------------------------

echo.
echo [4/4] Checking the client build

set "FAILED_STEP=client build"
if "%REBUILD%"=="1" (
  if exist "%DASHBOARD_DIR%\dist" (
    rmdir /s /q "%DASHBOARD_DIR%\dist"
    echo         Discarded the previous build.
  )
)

if not exist "%DASHBOARD_DIR%\dist\index.html" (
  echo         Building...
  pushd "%DASHBOARD_DIR%"
  call npm run build >"%LOG_FILE%" 2>&1
  set "NPM_STATUS=!ERRORLEVEL!"
  popd
  if not "!NPM_STATUS!"=="0" (
    call :banner "Client build failed"
    echo   vite build did not produce dashboard\dist\index.html.
    echo.
    echo     This usually means the dependency tree is incomplete or
    echo     mismatched. Reinstalling from scratch fixes most cases:
    echo.
    echo         rmdir /s /q dashboard\node_modules
    echo         rmdir /s /q dashboard\dist
    echo         dashboard\run.bat
    goto report
  )
  echo         Built.
) else (
  echo         Already built ^(use --rebuild to force a fresh one^).
)

if exist "%LOG_FILE%" del /q "%LOG_FILE%" >nul 2>&1

rem ---------------------------------------------------------------------------
rem Start
rem ---------------------------------------------------------------------------
rem
rem The server owns the port check: it is the process that binds, so it can
rem report a conflict precisely rather than racing a probe made here.

echo.
echo ------------------------------------------------------------
echo   Dashboard starting on http://localhost:%PORT%
echo ------------------------------------------------------------

set "BACKEND_PORT=%PORT%"
set "DASHBOARD_OPEN=%OPEN_BROWSER%"
uv run --extra backend python -m backend.app
set "EXIT_CODE=%ERRORLEVEL%"

rem A server that never started -- an occupied port is the usual reason --
rem printed its diagnosis and exited, and on an Explorer double-click the
rem window would close over it. Ctrl+C is a stop the reader asked for, and
rem cmd reports it as 130 or as 0; neither is held open.
if not "%EXIT_CODE%"=="0" if not "%EXIT_CODE%"=="130" (
  if not defined DASHBOARD_NONINTERACTIVE pause
)

popd
endlocal & exit /b %EXIT_CODE%

rem ---------------------------------------------------------------------------
rem Helpers
rem ---------------------------------------------------------------------------

:banner
echo.
echo ------------------------------------------------------------
echo   %~1
echo ------------------------------------------------------------
echo.
exit /b 0

rem Print the facts a bug report needs. This is what turns "it does not work"
rem into a reproducible report, so it is printed for the reader to copy rather
rem than left to be asked for afterwards.
:report
echo.
echo   If this persists, open an issue with the block below:
echo     %ISSUES_URL%
echo.
set "DASHBOARD_VERSION=unknown"
if exist "%REPO_ROOT%\VERSION" for /f "delims=" %%v in ('type "%REPO_ROOT%\VERSION"') do set "DASHBOARD_VERSION=%%v"
rem "git is absent" and "this is not a checkout" are separate facts, and
rem collapsing them sends a triager looking for a damaged clone when the real
rem answer is that the reporter downloaded a zip.
set "COMMIT=git is not installed"
where git >nul 2>&1
if not errorlevel 1 (
  set "COMMIT=not a git checkout"
  for /f "delims=" %%c in ('git -C "%REPO_ROOT%" rev-parse --short HEAD 2^>nul') do set "COMMIT=%%c"
)
set "NODE_REPORT=not installed"
for /f "delims=" %%v in ('node -v 2^>nul') do set "NODE_REPORT=%%v"
set "NPM_REPORT=not installed"
for /f "delims=" %%v in ('npm -v 2^>nul') do set "NPM_REPORT=%%v"
echo     dashboard      : %DASHBOARD_VERSION%
echo     commit         : %COMMIT%
echo     os             : %OS% %PROCESSOR_ARCHITECTURE%
echo     node           : %NODE_REPORT%
echo     npm            : %NPM_REPORT%
set "UV_REPORT=not installed"
for /f "delims=" %%v in ('uv --version 2^>nul') do set "UV_REPORT=%%v"
echo     uv             : %UV_REPORT%
echo     port requested : %PORT%
echo     failed step    : %FAILED_STEP%
if exist "%LOG_FILE%" (
  echo.
  echo   Last 20 lines of dashboard\.run.log:
  echo.
  powershell -NoProfile -Command "Get-Content -Tail 20 -LiteralPath '%LOG_FILE%' | ForEach-Object { '      ' + $_ }" 2>nul
)
echo.
rem Hold the window open, so a double-click from Explorer does not close it
rem before the diagnosis above can be read.
if not defined DASHBOARD_NONINTERACTIVE pause
popd
endlocal & exit /b 1
