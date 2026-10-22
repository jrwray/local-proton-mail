@echo off
rem Setup messages go to stderr so stdout stays clean for `pmail mcp`.
rem pmail for Windows: sets itself up on first use, then runs a command.
rem   pmail start | stop | status | sync | serve | draft ...   (see README)
rem Uses uv when it's installed, otherwise plain Python 3.11+.
setlocal
cd /d "%~dp0"
set "PMAIL_PY=%~dp0.venv\Scripts\python.exe"
call :ensure_env
if errorlevel 1 exit /b 1
"%PMAIL_PY%" -m pmail %*
exit /b %errorlevel%

:ensure_env
rem Ready when the venv runs and was set up from the current pyproject.toml.
"%PMAIL_PY%" -c "import imapclient, keyring, html2text" >nul 2>nul
if not errorlevel 1 (
  fc /b pyproject.toml .venv\pyproject.stamp >nul 2>nul
  if not errorlevel 1 exit /b 0
)
echo Setting up local-proton-mail (first run or after an update)... 1>&2
call :find_uv
if defined UV (
  "%UV%" sync --quiet --no-dev
  if errorlevel 1 exit /b 1
  goto :stamp
)
call :find_python
if not defined BASEPY (
  echo Python 3.11 or newer is needed. Install it from https://www.python.org/downloads/ and try again. 1>&2
  exit /b 1
)
if exist .venv rmdir /s /q .venv
%BASEPY% -m venv .venv
if errorlevel 1 exit /b 1
"%PMAIL_PY%" -c "import tomllib, subprocess, sys; deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; sys.exit(subprocess.call([sys.executable, '-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', *deps]))"
if errorlevel 1 exit /b 1
:stamp
copy /y pyproject.toml .venv\pyproject.stamp >nul
exit /b 0

:find_uv
for /f "delims=" %%U in ('where uv 2^>nul') do (set "UV=%%U" & exit /b 0)
for %%U in ("%USERPROFILE%\.local\bin\uv.exe" "%USERPROFILE%\.cargo\bin\uv.exe") do if exist %%U (set "UV=%%~U" & exit /b 0)
exit /b 0

:find_python
for %%C in ("py -3" "python" "python3") do (
  %%~C -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul && (set "BASEPY=%%~C" & exit /b 0)
)
exit /b 0
