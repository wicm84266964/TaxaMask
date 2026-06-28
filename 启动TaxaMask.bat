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
    "%USERPROFILE%\miniforge3\envs\taxamask\python.exe"
    "%USERPROFILE%\mambaforge\envs\taxamask\python.exe"
    "%ProgramData%\miniconda3\envs\taxamask\python.exe"
    "%ProgramData%\anaconda3\envs\taxamask\python.exe"
    "%ProgramData%\miniforge3\envs\taxamask\python.exe"
    "%ProgramData%\mambaforge\envs\taxamask\python.exe"
    "%USERPROFILE%\miniconda3\envs\antsleap\python.exe"
    "%USERPROFILE%\anaconda3\envs\antsleap\python.exe"
    "%ProgramData%\miniconda3\envs\antsleap\python.exe"
    "%ProgramData%\anaconda3\envs\antsleap\python.exe"
) do (
    if not defined PYTHON_EXE if exist "%%~P" set "PYTHON_EXE=%%~fP"
)

for %%C in (
    conda
    "%USERPROFILE%\miniconda3\condabin\conda.bat"
    "%USERPROFILE%\anaconda3\condabin\conda.bat"
    "%USERPROFILE%\miniforge3\condabin\conda.bat"
    "%USERPROFILE%\mambaforge\condabin\conda.bat"
    "%ProgramData%\miniconda3\condabin\conda.bat"
    "%ProgramData%\anaconda3\condabin\conda.bat"
    "%ProgramData%\miniforge3\condabin\conda.bat"
    "%ProgramData%\mambaforge\condabin\conda.bat"
) do (
    call :TryCondaEnvList "%%~C"
    if defined PYTHON_EXE goto PythonFound
)

for %%D in (C D E F G H) do (
    for %%C in (
        "%%D:\miniconda3\condabin\conda.bat"
        "%%D:\anaconda3\condabin\conda.bat"
        "%%D:\miniforge3\condabin\conda.bat"
        "%%D:\mambaforge\condabin\conda.bat"
        "%%D:\conda\condabin\conda.bat"
        "%%D:\Anaconda\condabin\conda.bat"
        "%%D:\Miniconda\condabin\conda.bat"
    ) do (
        call :TryCondaEnvList "%%~C"
        if defined PYTHON_EXE goto PythonFound
    )
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

for %%D in (C D E F G H) do (
    for /d %%E in (
        "%%D:\miniconda3\envs\taxamask*"
        "%%D:\anaconda3\envs\taxamask*"
        "%%D:\miniforge3\envs\taxamask*"
        "%%D:\mambaforge\envs\taxamask*"
        "%%D:\conda\envs\taxamask*"
        "%%D:\Anaconda\envs\taxamask*"
        "%%D:\Miniconda\envs\taxamask*"
        "%%D:\miniconda3\envs\antsleap*"
        "%%D:\anaconda3\envs\antsleap*"
    ) do (
        if not defined PYTHON_EXE if exist "%%~fE\python.exe" set "PYTHON_EXE=%%~fE\python.exe"
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

exit /b %ERRORLEVEL%

:TryCondaEnvList
set "TAXAMASK_CONDA_CANDIDATE=%~1"
if /i not "%TAXAMASK_CONDA_CANDIDATE%"=="conda" if not exist "%TAXAMASK_CONDA_CANDIDATE%" exit /b 1
for /f "delims=" %%E in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$conda=$env:TAXAMASK_CONDA_CANDIDATE; $raw=& $conda env list --json 2^>$null; if ($LASTEXITCODE -ne 0 -or -not $raw) { exit 0 }; $envs=($raw ^| ConvertFrom-Json).envs; foreach ($envPath in $envs) { $leaf=Split-Path -Leaf $envPath; if ($leaf -like 'taxamask*' -or $leaf -like 'antsleap*') { $envPath } }" 2^>nul') do (
    if not defined PYTHON_EXE if exist "%%E\python.exe" set "PYTHON_EXE=%%E\python.exe"
    if defined PYTHON_EXE exit /b 0
)
exit /b 1
