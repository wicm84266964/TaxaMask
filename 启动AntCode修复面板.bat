@echo off
setlocal

cd /d "%~dp0"

set "PROJECT_ROOT=%CD%"
set "ANT_CODE_ROOT=%PROJECT_ROOT%\vendor\ant-code"
set "DASHBOARD_ENTRY=%ANT_CODE_ROOT%\src\cli\dashboard.js"
set "NODE_EXE="
set "PORT=7410"

if defined TAXAMASK_ANTCODE_PORT set "PORT=%TAXAMASK_ANTCODE_PORT%"

if not exist "%DASHBOARD_ENTRY%" (
    echo Cannot find the bundled Ant-Code dashboard entry:
    echo %DASHBOARD_ENTRY%
    echo.
    echo Make sure vendor\ant-code is included with this TaxaMask copy.
    pause
    exit /b 1
)

if defined TAXAMASK_NODE_EXE (
    if exist "%TAXAMASK_NODE_EXE%" set "NODE_EXE=%TAXAMASK_NODE_EXE%"
)

for %%N in (
    "%ANT_CODE_ROOT%\node.exe"
    "%PROJECT_ROOT%\node.exe"
    "%ProgramFiles%\nodejs\node.exe"
    "%ProgramFiles(x86)%\nodejs\node.exe"
    "%LocalAppData%\Programs\nodejs\node.exe"
) do (
    if not defined NODE_EXE if exist "%%~N" set "NODE_EXE=%%~fN"
)

if not defined NODE_EXE (
    for %%C in (node.exe node) do (
        if not defined NODE_EXE (
            for /f "delims=" %%F in ('where %%C 2^>nul') do (
                if not defined NODE_EXE set "NODE_EXE=%%F"
            )
        )
    )
)

if not defined NODE_EXE (
    echo Cannot find Node.js.
    echo.
    echo This recovery script does not need PySide6 or the TaxaMask GUI,
    echo but it does need Node.js 20 or newer to run the bundled Ant-Code dashboard.
    echo You can also set TAXAMASK_NODE_EXE to the full path of node.exe.
    echo.
    pause
    exit /b 1
)

"%NODE_EXE%" -e "const major=Number(process.versions.node.split('.')[0]); process.exit(major>=20?0:1)"
if errorlevel 1 (
    echo Node.js 20 or newer is required.
    echo Current Node executable:
    echo %NODE_EXE%
    echo.
    "%NODE_EXE%" -v
    pause
    exit /b 1
)

set "LAB_AGENT_PACKAGE_ROOT=%ANT_CODE_ROOT%"
set "LAB_AGENT_SKIP_PROJECT_CONFIG=1"

echo Starting Ant-Code recovery dashboard for TaxaMask...
echo Project: %PROJECT_ROOT%
echo Node: %NODE_EXE%
echo Port: %PORT% ^(if busy, Ant-Code will try the next available port^)
echo.
echo Keep this window open while using the dashboard.
echo Close this window to stop the local dashboard server.
echo.

"%NODE_EXE%" "%DASHBOARD_ENTRY%" --project "%PROJECT_ROOT%" --port "%PORT%"

if errorlevel 1 (
    echo.
    echo Ant-Code dashboard exited with an error. Check the messages above.
    pause
)
