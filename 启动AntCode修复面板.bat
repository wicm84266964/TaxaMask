@echo off
setlocal

cd /d "%~dp0"

set "PROJECT_ROOT=%CD%"
set "ANT_CODE_ROOT=%PROJECT_ROOT%\vendor\ant-code"
set "DASHBOARD_ENTRY=%ANT_CODE_ROOT%\src\cli\dashboard-embed.ts"
if not exist "%DASHBOARD_ENTRY%" set "DASHBOARD_ENTRY=%ANT_CODE_ROOT%\src\cli\index.ts"
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

if defined TAXAMASK_NODE_EXE call :AcceptNode "%TAXAMASK_NODE_EXE%"

for %%N in (
    "%CONDA_PREFIX%\node.exe"
    "%ANT_CODE_ROOT%\node.exe"
    "%PROJECT_ROOT%\node.exe"
    "%USERPROFILE%\anaconda3\envs\taxamask\node.exe"
    "%USERPROFILE%\miniconda3\envs\taxamask\node.exe"
    "%ProgramFiles%\nodejs\node.exe"
    "%ProgramFiles(x86)%\nodejs\node.exe"
    "%LocalAppData%\Programs\nodejs\node.exe"
) do (
    if not defined NODE_EXE call :AcceptNode "%%~N"
)

if not defined NODE_EXE (
    for %%C in (node.exe node) do (
        for /f "delims=" %%F in ('where %%C 2^>nul') do (
            if not defined NODE_EXE call :AcceptNode "%%F"
        )
    )
)

if not defined NODE_EXE (
    echo Cannot find Node.js.
    echo.
    echo This recovery script does not need PySide6 or the TaxaMask GUI,
    echo but it does need Node.js 22.18 or newer to run the bundled Ant-Code dashboard.
    echo You can also set TAXAMASK_NODE_EXE to the full path of node.exe.
    echo.
    pause
    exit /b 1
)

goto NodeReady

:AcceptNode
if "%~1"=="" exit /b 1
if not exist "%~1" exit /b 1
"%~1" -e "const [major,minor]=process.versions.node.split('.').map(Number); process.exit((major>22||(major===22&&minor>=18))?0:1)" >nul 2>nul
if errorlevel 1 exit /b 1
set "NODE_EXE=%~f1"
exit /b 0

:NodeReady

set "LAB_AGENT_PACKAGE_ROOT=%ANT_CODE_ROOT%"
set "LAB_AGENT_CONFIG=%PROJECT_ROOT%\AntSleap\config\taxamask_ant_code.config.json"
if defined LOCALAPPDATA (
    set "NODE_COMPILE_CACHE=%LOCALAPPDATA%\TaxaMask\ant-code-compile-cache"
) else (
    set "NODE_COMPILE_CACHE=%USERPROFILE%\.cache\TaxaMask\ant-code-compile-cache"
)
if not exist "%NODE_COMPILE_CACHE%" mkdir "%NODE_COMPILE_CACHE%" >nul 2>&1

echo Starting Ant-Code recovery dashboard for TaxaMask...
echo Project: %PROJECT_ROOT%
echo Node: %NODE_EXE%
echo Port: %PORT% ^(if busy, Ant-Code will try the next available port^)
echo.
echo Keep this window open while using the dashboard.
echo Close this window to stop the local dashboard server.
echo.

if /I "%DASHBOARD_ENTRY:~-8%"=="index.ts" (
    "%NODE_EXE%" --experimental-strip-types --disable-warning=ExperimentalWarning "%DASHBOARD_ENTRY%" dashboard --project "%PROJECT_ROOT%" --port "%PORT%"
) else (
    "%NODE_EXE%" --experimental-strip-types --disable-warning=ExperimentalWarning "%DASHBOARD_ENTRY%" --project "%PROJECT_ROOT%" --port "%PORT%"
)

if errorlevel 1 (
    echo.
    echo Ant-Code dashboard exited with an error. Check the messages above.
    pause
)
