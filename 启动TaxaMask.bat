@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE="

if defined TAXAMASK_PYTHON_EXE (
    if exist "%TAXAMASK_PYTHON_EXE%" set "PYTHON_EXE=%TAXAMASK_PYTHON_EXE%"
)

for %%P in (
    "%~dp0.venv\Scripts\python.exe"
    "%~dp0venv\Scripts\python.exe"
    "%~dp0env\Scripts\python.exe"
    "%CONDA_PREFIX%\python.exe"
    "%USERPROFILE%\miniconda3\envs\taxamask\python.exe"
    "%USERPROFILE%\anaconda3\envs\taxamask\python.exe"
    "%ProgramData%\miniconda3\envs\taxamask\python.exe"
    "%ProgramData%\anaconda3\envs\taxamask\python.exe"
    "%USERPROFILE%\miniconda3\envs\antsleap\python.exe"
    "%USERPROFILE%\anaconda3\envs\antsleap\python.exe"
    "%ProgramData%\miniconda3\envs\antsleap\python.exe"
    "%ProgramData%\anaconda3\envs\antsleap\python.exe"
) do (
    if not defined PYTHON_EXE if exist "%%~P" set "PYTHON_EXE=%%~fP"
)

if not defined PYTHON_EXE (
    for %%C in (python.exe python py.exe) do (
        if not defined PYTHON_EXE (
            for /f "delims=" %%F in ('where %%C 2^>nul') do (
                if not defined PYTHON_EXE set "PYTHON_EXE=%%F"
            )
        )
    )
)

if not defined PYTHON_EXE (
    echo Cannot find a Python executable for TaxaMask.
    echo.
    echo Recommended options:
    echo   1. Create a local .venv or a taxamask Conda environment.
    echo   2. Set TAXAMASK_PYTHON_EXE to the full path of python.exe before running this script.
    echo   3. Run python AntSleap\main.py from an already configured terminal.
    echo.
    pause
    exit /b 1
)

for %%I in ("%PYTHON_EXE%") do set "PYTHON_DIR=%%~dpI"
if exist "%PYTHON_DIR%conda-meta" (
    set "CONDA_PREFIX=%PYTHON_DIR:~0,-1%"
    for %%E in ("%CONDA_PREFIX%") do set "CONDA_DEFAULT_ENV=%%~nxE"
    set "CONDA_SHLVL=1"
)
set "PATH=%PYTHON_DIR%;%PYTHON_DIR%Library\mingw-w64\bin;%PYTHON_DIR%Library\usr\bin;%PYTHON_DIR%Library\bin;%PYTHON_DIR%Scripts;%PATH%"

set "__NV_PRIME_RENDER_OFFLOAD=1"
set "__GLX_VENDOR_LIBRARY_NAME=nvidia"
set "QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu-compositing"
if not defined TAXAMASK_ENABLE_TIF_WORKFLOW set "TAXAMASK_ENABLE_TIF_WORKFLOW=1"

echo Starting TaxaMask with:
echo %PYTHON_EXE%
echo.

"%PYTHON_EXE%" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo The selected Python cannot import PySide6:
    echo %PYTHON_EXE%
    echo.
    echo Please install TaxaMask dependencies in this environment, choose another Python
    echo with TAXAMASK_PYTHON_EXE, or run from a configured terminal.
    echo.
    echo If TaxaMask was broken by source-code changes, run:
    echo   启动AntCode修复面板.bat
    pause
    exit /b 1
)

"%PYTHON_EXE%" AntSleap\main.py

if errorlevel 1 (
    echo.
    echo TaxaMask exited with an error. Check the messages above.
    echo If the GUI cannot start after source-code changes, run:
    echo   启动AntCode修复面板.bat
    pause
)
