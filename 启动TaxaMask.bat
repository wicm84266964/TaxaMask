@echo off
setlocal

cd /d "%~dp0"

set "CONDA_ROOT=%USERPROFILE%\anaconda3"
if not exist "%CONDA_ROOT%\envs\antsleap\python.exe" set "CONDA_ROOT=%USERPROFILE%\miniconda3"
if not exist "%CONDA_ROOT%\envs\antsleap\python.exe" set "CONDA_ROOT=C:\Users\admin\anaconda3"

set "ANTSLEAP_ENV=%CONDA_ROOT%\envs\antsleap"
set "PYTHON_EXE=%ANTSLEAP_ENV%\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Cannot find the Conda environment Python:
    echo %PYTHON_EXE%
    echo.
    echo Please edit this file and set CONDA_ROOT to your Conda installation.
    pause
    exit /b 1
)

set "CONDA_DEFAULT_ENV=antsleap"
set "CONDA_PREFIX=%ANTSLEAP_ENV%"
set "CONDA_SHLVL=1"
set "PATH=%ANTSLEAP_ENV%;%ANTSLEAP_ENV%\Library\mingw-w64\bin;%ANTSLEAP_ENV%\Library\usr\bin;%ANTSLEAP_ENV%\Library\bin;%ANTSLEAP_ENV%\Scripts;%PATH%"

set "__NV_PRIME_RENDER_OFFLOAD=1"
set "__GLX_VENDOR_LIBRARY_NAME=nvidia"
set "QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu-compositing"

"%PYTHON_EXE%" AntSleap\main.py

if errorlevel 1 (
    echo.
    echo TaxaMask exited with an error. Check the messages above.
    pause
)
