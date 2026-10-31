@echo off
rem SPDX-License-Identifier: Apache-2.0
rem ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
rem ai-sandbox bootstrap for Windows - plain cmd.exe, no PowerShell, no Python required.
rem
rem   cd C:\path\to\your-project
rem   C:\path\to\install.cmd            (same as: aisb init)
rem   C:\path\to\install.cmd verify     (any aisb command)
rem
rem 1. If Python 3.8+ exists (py launcher or python on PATH): run aisb from this checkout or a downloaded aisb.pyz.
rem 2. Otherwise download the standalone build for this CPU from GitHub Releases (curl.exe / certutil / bitsadmin),
rem    verify it against SHA256SUMS (certutil), extract with tar.exe (Windows 10 1803+) and run it.
rem    Nothing is installed outside this folder; no registry, no PATH, no admin rights.
rem Override:  set AISB_REPO=owner/repo   set AISB_VERSION=v1.2.3   set AISB_BASE_URL=<custom base url>
setlocal EnableExtensions
set "HERE=%~dp0"
set "PROJ=%CD%"
if "%AISB_REPO%"=="" set "AISB_REPO=RATEESHK/ai-sandbox"
if "%AISB_VERSION%"=="" set "AISB_VERSION=latest"
if not "%AISB_BASE_URL%"=="" ( set "BASE=%AISB_BASE_URL%" ) else (
  if /I "%AISB_VERSION%"=="latest" ( set "BASE=https://github.com/%AISB_REPO%/releases/latest/download" ) else ( set "BASE=https://github.com/%AISB_REPO%/releases/download/%AISB_VERSION%" )
)
set "ARGS=%*"
if "%ARGS%"=="" set "ARGS=init"
if /I "%~1"=="-h" goto :help
if /I "%~1"=="--help" goto :help
if /I "%~1"=="help" goto :help

if /I "%HERE%"=="%PROJ%\" if exist "%HERE%aisb\cli.py" if not exist "%HERE%.ai-sandbox\policy.json" (
  echo install.cmd: you are inside the ai-sandbox repository itself. Run it from the project you want to sandbox: 1>&2
  echo     cd C:\path\to\your\project ^&^& "%~f0" 1>&2
  exit /b 1
)

rem ---- 1. Python path ----------------------------------------------------------------------
set "PY="
set "PYARGS="
if exist "%PROJ%\.venv\Scripts\python.exe" ( set "PY=%PROJ%\.venv\Scripts\python.exe" & call :pycheck && goto :havepy )
if exist "%PROJ%\.ai-sandbox\runtime\python\python.exe" ( set "PY=%PROJ%\.ai-sandbox\runtime\python\python.exe" & call :pycheck && goto :havepy )
where py >nul 2>nul && ( set "PY=py" & set "PYARGS=-3" & call :pycheck && goto :havepy )
where python >nul 2>nul && ( set "PY=python" & set "PYARGS=" & call :pycheck && goto :havepy )
where python3 >nul 2>nul && ( set "PY=python3" & set "PYARGS=" & call :pycheck && goto :havepy )
goto :standalone

:havepy
if exist "%HERE%aisb\cli.py" (
  set "PYTHONPATH=%HERE%;%PYTHONPATH%"
  "%PY%" %PYARGS% -m aisb %ARGS%
  exit /b %ERRORLEVEL%
)
if exist "%PROJ%\.ai-sandbox\bin\aisb.pyz" ( "%PY%" %PYARGS% "%PROJ%\.ai-sandbox\bin\aisb.pyz" %ARGS% & exit /b %ERRORLEVEL% )
if exist "%HERE%aisb.pyz" ( "%PY%" %PYARGS% "%HERE%aisb.pyz" %ARGS% & exit /b %ERRORLEVEL% )
set "TMPD=%PROJ%\.ai-sandbox-bootstrap"
if not exist "%TMPD%" mkdir "%TMPD%"
echo install.cmd: downloading aisb.pyz from %BASE% ...
call :fetch "%BASE%/SHA256SUMS" "%TMPD%\SHA256SUMS" || goto :fail
call :fetch "%BASE%/aisb.pyz" "%TMPD%\aisb.pyz" || goto :fail
call :verify "%TMPD%\aisb.pyz" aisb.pyz "%TMPD%\SHA256SUMS" || goto :fail
"%PY%" %PYARGS% "%TMPD%\aisb.pyz" %ARGS%
set "RC=%ERRORLEVEL%"
rmdir /s /q "%TMPD%" >nul 2>nul
exit /b %RC%

rem ---- 2. No Python: standalone build ---------------------------------------------------------
:standalone
set "ARCH=x64"
if /I "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "ARCH=arm64"
if /I "%PROCESSOR_ARCHITEW6432%"=="ARM64" set "ARCH=arm64"
set "ASSET=aisb-windows-%ARCH%.zip"
set "DEST=%PROJ%\.ai-sandbox\bin\aisb-bin"
if exist "%DEST%\aisb.exe" ( "%DEST%\aisb.exe" %ARGS% & exit /b %ERRORLEVEL% )
echo install.cmd: no Python 3.8+ found; downloading the standalone build %ASSET% from %BASE% ...
set "TMPD=%PROJ%\.ai-sandbox-bootstrap"
if not exist "%TMPD%" mkdir "%TMPD%"
call :fetch "%BASE%/SHA256SUMS" "%TMPD%\SHA256SUMS" || goto :fail
call :fetch "%BASE%/%ASSET%" "%TMPD%\%ASSET%" || goto :fail
call :verify "%TMPD%\%ASSET%" %ASSET% "%TMPD%\SHA256SUMS" || goto :fail
if exist "%TMPD%\unpacked" rmdir /s /q "%TMPD%\unpacked"
mkdir "%TMPD%\unpacked"
where tar >nul 2>nul && ( tar -xf "%TMPD%\%ASSET%" -C "%TMPD%\unpacked" ) || (
  where powershell >nul 2>nul && ( powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%TMPD%\%ASSET%' -DestinationPath '%TMPD%\unpacked' -Force" ) || (
    echo install.cmd: neither tar.exe nor PowerShell is available to extract %ASSET%. Unzip it yourself into "%DEST%" and re-run. 1>&2
    goto :fail
  )
)
if exist "%DEST%" rmdir /s /q "%DEST%"
if not exist "%PROJ%\.ai-sandbox\bin" mkdir "%PROJ%\.ai-sandbox\bin"
if exist "%TMPD%\unpacked\aisb-bin\aisb.exe" ( move /y "%TMPD%\unpacked\aisb-bin" "%DEST%" >nul ) else ( move /y "%TMPD%\unpacked" "%DEST%" >nul )
rmdir /s /q "%TMPD%" >nul 2>nul
if not exist "%DEST%\aisb.exe" ( echo install.cmd: aisb.exe not found after extraction 1>&2 & exit /b 1 )
echo install.cmd: standalone aisb ready at %DEST% (project-local; delete the folder to remove it)
"%DEST%\aisb.exe" %ARGS%
exit /b %ERRORLEVEL%

rem ---- helpers --------------------------------------------------------------------------------
:pycheck
"%PY%" %PYARGS% -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
if errorlevel 1 ( set "PY=" & set "PYARGS=" & exit /b 1 )
exit /b 0

:fetch
rem :fetch URL DEST  - curl.exe (Win10 1803+), then certutil, then bitsadmin, then PowerShell
if exist "%~2" del /q "%~2"
where curl >nul 2>nul && ( curl -fsSL --retry 3 -o "%~2" "%~1" >nul 2>nul && if exist "%~2" exit /b 0 )
certutil -urlcache -split -f "%~1" "%~2" >nul 2>nul && if exist "%~2" exit /b 0
bitsadmin /transfer aisb /download /priority foreground "%~1" "%~2" >nul 2>nul && if exist "%~2" exit /b 0
where powershell >nul 2>nul && ( powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -UseBasicParsing -Uri '%~1' -OutFile '%~2'" >nul 2>nul && if exist "%~2" exit /b 0 )
echo install.cmd: could not download %~1 (tried curl, certutil, bitsadmin, PowerShell). Download it yourself to "%~2" and re-run. 1>&2
exit /b 1

:verify
rem :verify FILE NAME SUMSFILE  - compare certutil's SHA256 with the line in SHA256SUMS
setlocal EnableDelayedExpansion
set "WANT="
for /f "usebackq tokens=1,2" %%a in ("%~3") do ( if /I "%%b"=="%~2" set "WANT=%%a" )
if "!WANT!"=="" ( echo install.cmd: %~2 is not listed in SHA256SUMS - refusing 1>&2 & endlocal & exit /b 1 )
set "GOT="
for /f "skip=1 delims=" %%h in ('certutil -hashfile "%~1" SHA256') do ( if "!GOT!"=="" set "GOT=%%h" )
set "GOT=!GOT: =!"
if /I not "!GOT!"=="!WANT!" ( echo install.cmd: SHA256 mismatch for %~2 ^(expected !WANT!, got !GOT!^) - refusing 1>&2 & endlocal & exit /b 1 )
endlocal
exit /b 0

:fail
call :fetch "%BASE%/aisb.pyz" "%TMPD%\aisb.pyz" || goto :fail
call :verify "%TMPD%\aisb.pyz" aisb.pyz "%TMPD%\SHA256SUMS" || goto :fail
"%PY%" %PYARGS% "%TMPD%\aisb.pyz" %ARGS%
set "RC=%ERRORLEVEL%"
rmdir /s /q "%TMPD%" >nul 2>nul
exit /b %RC%

rem ---- 2. No Python: standalone build ---------------------------------------------------------
:standalone
set "ARCH=x64"
if /I "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "ARCH=arm64"
if /I "%PROCESSOR_ARCHITEW6432%"=="ARM64" set "ARCH=arm64"
set "ASSET=aisb-windows-%ARCH%.zip"
set "DEST=%PROJ%\.ai-sandbox\bin\aisb-bin"
if exist "%DEST%\aisb.exe" ( "%DEST%\aisb.exe" %ARGS% & exit /b %ERRORLEVEL% )
echo install.cmd: no Python 3.8+ found; downloading the standalone build %ASSET% from %BASE% ...
set "TMPD=%PROJ%\.ai-sandbox-bootstrap"
if not exist "%TMPD%" mkdir "%TMPD%"
call :fetch "%BASE%/SHA256SUMS" "%TMPD%\SHA256SUMS" || goto :fail
call :fetch "%BASE%/%ASSET%" "%TMPD%\%ASSET%" || goto :fail
call :verify "%TMPD%\%ASSET%" %ASSET% "%TMPD%\SHA256SUMS" || goto :fail
if exist "%TMPD%\unpacked" rmdir /s /q "%TMPD%\unpacked"
mkdir "%TMPD%\unpacked"
where tar >nul 2>nul && ( tar -xf "%TMPD%\%ASSET%" -C "%TMPD%\unpacked" ) || (
  where powershell >nul 2>nul && ( powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%TMPD%\%ASSET%' -DestinationPath '%TMPD%\unpacked' -Force" ) || (
    echo install.cmd: neither tar.exe nor PowerShell is available to extract %ASSET%. Unzip it yourself into "%DEST%" and re-run. 1>&2
    goto :fail
  )
)
if exist "%DEST%" rmdir /s /q "%DEST%"
if not exist "%PROJ%\.ai-sandbox\bin" mkdir "%PROJ%\.ai-sandbox\bin"
if exist "%TMPD%\unpacked\aisb-bin\aisb.exe" ( move /y "%TMPD%\unpacked\aisb-bin" "%DEST%" >nul ) else ( move /y "%TMPD%\unpacked" "%DEST%" >nul )
rmdir /s /q "%TMPD%" >nul 2>nul
if not exist "%DEST%\aisb.exe" ( echo install.cmd: aisb.exe not found after extraction 1>&2 & exit /b 1 )
echo install.cmd: standalone aisb ready at %DEST% (project-local; delete the folder to remove it)
"%DEST%\aisb.exe" %ARGS%
exit /b %ERRORLEVEL%

rem ---- helpers --------------------------------------------------------------------------------
:pycheck
"%PY%" %PYARGS% -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
if errorlevel 1 ( set "PY=" & set "PYARGS=" & exit /b 1 )
exit /b 0

:fetch
rem :fetch URL DEST  - curl.exe (Win10 1803+), then certutil, then bitsadmin, then PowerShell
if exist "%~2" del /q "%~2"
where curl >nul 2>nul && ( curl -fsSL --retry 3 -o "%~2" "%~1" >nul 2>nul && if exist "%~2" exit /b 0 )
certutil -urlcache -split -f "%~1" "%~2" >nul 2>nul && if exist "%~2" exit /b 0
bitsadmin /transfer aisb /download /priority foreground "%~1" "%~2" >nul 2>nul && if exist "%~2" exit /b 0
where powershell >nul 2>nul && ( powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -UseBasicParsing -Uri '%~1' -OutFile '%~2'" >nul 2>nul && if exist "%~2" exit /b 0 )
echo install.cmd: could not download %~1 (tried curl, certutil, bitsadmin, PowerShell). Download it yourself to "%~2" and re-run. 1>&2
exit /b 1

:verify
rem :verify FILE NAME SUMSFILE  - compare certutil SHA256 with the line in SHA256SUMS
set "WANT="
for /f "usebackq tokens=1,2" %%a in ("%~3") do ( if /I "%%b"=="%~2" set "WANT=%%a" )
if "%WANT%"=="" ( echo install.cmd: %~2 is not listed in SHA256SUMS - refusing 1>&2 & exit /b 1 )
set "GOT="
for /f "skip=1 tokens=1" %%h in ('certutil -hashfile "%~1" SHA256 ^| findstr /v /i "certutil"') do ( if "!GOT!"=="" set "GOT=%%h" )
setlocal EnableDelayedExpansion
for /f "skip=1 tokens=1" %%h in ('certutil -hashfile "%~1" SHA256 ^| findstr /v /i "certutil"') do ( if "!GOT!"=="" set "GOT=%%h" )
if /I not "!GOT!"=="%WANT%" ( echo install.cmd: SHA256 mismatch for %~2 ^(expected %WANT%, got !GOT!^) - refusing 1>&2 & endlocal & exit /b 1 )
endlocal
exit /b 0

:fail
rmdir /s /q "%PROJ%\.ai-sandbox-bootstrap" >nul 2>nul
exit /b 1

:help
echo ai-sandbox bootstrap (Windows cmd). Run it from your project folder:
echo     cd C:\path\to\your-project
echo     "%~f0"            (= aisb init)      "%~f0" verify      "%~f0" doctor antigravity
echo Uses Python 3.8+ when present, otherwise downloads the standalone build into .ai-sandbox\bin\aisb-bin.
exit /b 0
