$ErrorActionPreference = "Stop"

$env:QT_OPENGL = "desktop"
$env:__NV_PRIME_RENDER_OFFLOAD = "1"
$env:__GLX_VENDOR_LIBRARY_NAME = "nvidia"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$main = Join-Path $repo "AntSleap\main.py"

$candidates = @()
if ($env:TAXAMASK_PYTHON_EXE) {
    $candidates += $env:TAXAMASK_PYTHON_EXE
}
if ($env:CONDA_PREFIX) {
    $candidates += (Join-Path $env:CONDA_PREFIX "pythonw.exe")
    $candidates += (Join-Path $env:CONDA_PREFIX "python.exe")
}
$candidates += (Join-Path $repo ".venv\Scripts\pythonw.exe")
$candidates += (Join-Path $repo ".venv\Scripts\python.exe")
$candidates += (Join-Path $env:USERPROFILE "miniconda3\envs\taxamask\pythonw.exe")
$candidates += (Join-Path $env:USERPROFILE "anaconda3\envs\taxamask\pythonw.exe")

$python = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $python) {
    $python = (Get-Command pythonw.exe -ErrorAction SilentlyContinue | Select-Object -First 1).Source
}
if (-not $python) {
    $python = (Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1).Source
}
if (-not $python) {
    throw "Cannot find Python. Set TAXAMASK_PYTHON_EXE to python.exe or pythonw.exe."
}

Start-Process -FilePath $python -ArgumentList @($main) -WorkingDirectory $repo -WindowStyle Hidden
