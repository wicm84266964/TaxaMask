@echo off
setlocal

chcp 65001 >nul
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
    "%ProgramData%\miniconda3\envs\taxamask\python.exe"
    "%ProgramData%\anaconda3\envs\taxamask\python.exe"
) do (
    call :TryPython "%%~P" "known environment path" 0
    if defined PYTHON_EXE goto PythonFound
)

for /d %%E in (
    "%USERPROFILE%\miniconda3\envs\taxamask*"
    "%USERPROFILE%\anaconda3\envs\taxamask*"
    "%USERPROFILE%\miniforge3\envs\taxamask*"
    "%USERPROFILE%\mambaforge\envs\taxamask*"
    "%USERPROFILE%\.conda\envs\taxamask*"
    "%ProgramData%\miniconda3\envs\taxamask*"
    "%ProgramData%\anaconda3\envs\taxamask*"
) do (
    call :TryPython "%%~fE\python.exe" "named conda env %%~nxE" 0
    if defined PYTHON_EXE goto PythonFound
)

if not defined PYTHON_EXE (
    for %%C in (python.exe python py.exe) do (
        if not defined PYTHON_EXE (
            for /f "delims=" %%F in ('where %%C 2^>nul') do (
                call :TryPython "%%F" "PATH %%C" 0
                if defined PYTHON_EXE goto PythonFound
            )
        )
    )
)

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
