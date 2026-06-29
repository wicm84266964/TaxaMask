@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE="
set "PYTHON_SOURCE="

if defined TAXAMASK_PYTHON_EXE (
    call :TryPython "%TAXAMASK_PYTHON_EXE%" "TAXAMASK_PYTHON_EXE" 1
    if defined PYTHON_EXE goto PythonFound
    echo TAXAMASK_PYTHON_EXE was set but does not look like a complete TaxaMask environment.
    echo.
    pause
    exit /b 1
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
    if not defined PYTHON_EXE call :TryPython "%%~P" "known environment path" 0
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
    if not defined PYTHON_EXE call :TryCondaEnvList "%%~C"
)

if not defined PYTHON_EXE for %%D in (C D E F G H) do (
    for %%E in (
        "%%D:\miniconda3\envs\taxamask\python.exe"
        "%%D:\anaconda3\envs\taxamask\python.exe"
        "%%D:\miniforge3\envs\taxamask\python.exe"
        "%%D:\mambaforge\envs\taxamask\python.exe"
        "%%D:\conda\envs\taxamask\python.exe"
        "%%D:\Anaconda\envs\taxamask\python.exe"
        "%%D:\Miniconda\envs\taxamask\python.exe"
        "%%D:\miniconda3\envs\antsleap\python.exe"
        "%%D:\anaconda3\envs\antsleap\python.exe"
    ) do (
        if not defined PYTHON_EXE call :TryPython "%%~fE" "drive known environment path" 0
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
        if not defined PYTHON_EXE call :TryPython "%%~fE\python.exe" "drive conda env %%~fE" 0
    )
)

if not defined PYTHON_EXE (
    for %%C in (python.exe python py.exe) do (
        if not defined PYTHON_EXE (
            for /f "delims=" %%F in ('where %%C 2^>nul') do (
                if not defined PYTHON_EXE call :TryPython "%%F" "PATH %%C" 0
            )
        )
    )
)

if defined PYTHON_EXE goto PythonFound

if not defined PYTHON_EXE (
    echo Cannot find a Python environment with the minimum TaxaMask dependencies.
    echo.
    echo Recommended options:
    echo   1. Activate your Conda environment first, then run this script.
    echo   2. Set TAXAMASK_PYTHON_EXE to the full path of that environment's python.exe.
    echo   3. Create a local .venv or a Conda environment named taxamask.
    echo   4. Run python AntSleap\main.py from an already configured terminal.
    echo.
    pause
    exit /b 1
)

:PythonFound
for %%I in ("%PYTHON_EXE%") do set "PYTHON_DIR=%%~dpI"
set "PYTHON_ROOT=%PYTHON_DIR:~0,-1%"
for %%I in ("%PYTHON_DIR%..") do if exist "%%~fI\pyvenv.cfg" set "PYTHON_ROOT=%%~fI"
if exist "%PYTHON_ROOT%\conda-meta" (
    set "CONDA_PREFIX=%PYTHON_ROOT%"
    for %%I in ("%PYTHON_ROOT%") do set "CONDA_DEFAULT_ENV=%%~nxI"
    set "CONDA_SHLVL=1"
)
set "PATH=%PYTHON_DIR%;%PYTHON_ROOT%\Library\mingw-w64\bin;%PYTHON_ROOT%\Library\usr\bin;%PYTHON_ROOT%\Library\bin;%PYTHON_ROOT%\Scripts;%PATH%"

set "__NV_PRIME_RENDER_OFFLOAD=1"
set "__GLX_VENDOR_LIBRARY_NAME=nvidia"
set "QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu-compositing"
if not defined TAXAMASK_ENABLE_TIF_WORKFLOW set "TAXAMASK_ENABLE_TIF_WORKFLOW=1"

echo Starting TaxaMask with:
echo %PYTHON_EXE%
if defined PYTHON_SOURCE echo Source: %PYTHON_SOURCE%
echo.

"%PYTHON_EXE%" AntSleap\main.py

if errorlevel 1 (
    echo.
    echo TaxaMask exited with an error. Check the messages above.
    echo If the GUI cannot start after source-code changes, run:
    echo   启动AntCode修复面板.bat
    pause
)

exit /b %ERRORLEVEL%

:TryPython
set "CANDIDATE_PYTHON=%~1"
set "CANDIDATE_SOURCE=%~2"
set "STRICT_CANDIDATE=%~3"
if not exist "%CANDIDATE_PYTHON%" exit /b 1
"%CANDIDATE_PYTHON%" -c "import PySide6, numpy, cv2, PIL, matplotlib, requests; import fitz, pdfplumber" >nul 2>nul
if errorlevel 1 (
    if "%STRICT_CANDIDATE%"=="1" (
        echo Selected Python is missing one or more minimum TaxaMask dependencies:
        echo %CANDIDATE_PYTHON%
    ) else (
        echo Skipping Python without minimum TaxaMask dependencies: %CANDIDATE_PYTHON%
    )
    exit /b 1
)
set "PYTHON_EXE=%CANDIDATE_PYTHON%"
set "PYTHON_SOURCE=%CANDIDATE_SOURCE%"
exit /b 0

:TryCondaEnvList
set "TAXAMASK_CONDA_CANDIDATE=%~1"
if /i not "%TAXAMASK_CONDA_CANDIDATE%"=="conda" if not exist "%TAXAMASK_CONDA_CANDIDATE%" exit /b 1
for /f "delims=" %%E in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$conda=$env:TAXAMASK_CONDA_CANDIDATE; $raw=& $conda env list --json 2^>$null; if ($LASTEXITCODE -ne 0 -or -not $raw) { exit 0 }; $envs=($raw ^| ConvertFrom-Json).envs; foreach ($envPath in $envs) { $leaf=Split-Path -Leaf $envPath; if ($leaf -like 'taxamask*' -or $leaf -like 'antsleap*') { $envPath } }" 2^>nul') do (
    call :TryPython "%%E\python.exe" "conda env list %%E" 0
    if defined PYTHON_EXE exit /b 0
)
exit /b 1
