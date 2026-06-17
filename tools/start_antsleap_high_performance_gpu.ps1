$ErrorActionPreference = "Stop"

$env:QT_OPENGL = "desktop"
$env:__NV_PRIME_RENDER_OFFLOAD = "1"
$env:__GLX_VENDOR_LIBRARY_NAME = "nvidia"
if (-not $env:TAXAMASK_ENABLE_TIF_WORKFLOW) {
    $env:TAXAMASK_ENABLE_TIF_WORKFLOW = "1"
}

$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$main = Join-Path $repo "AntSleap\main.py"

function Find-TaxaMaskPythonw {
    if ($env:TAXAMASK_PYTHONW_EXE -and (Test-Path -LiteralPath $env:TAXAMASK_PYTHONW_EXE)) {
        return (Resolve-Path -LiteralPath $env:TAXAMASK_PYTHONW_EXE).Path
    }

    if ($env:TAXAMASK_PYTHON_EXE -and (Test-Path -LiteralPath $env:TAXAMASK_PYTHON_EXE)) {
        $pythonDir = Split-Path -Parent $env:TAXAMASK_PYTHON_EXE
        $candidate = Join-Path $pythonDir "pythonw.exe"
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
        return (Resolve-Path -LiteralPath $env:TAXAMASK_PYTHON_EXE).Path
    }

    $candidatePaths = @(
        (Join-Path $repo ".venv\Scripts\pythonw.exe"),
        (Join-Path $repo "venv\Scripts\pythonw.exe"),
        (Join-Path $repo "env\Scripts\pythonw.exe")
    )

    if ($env:CONDA_PREFIX) {
        $candidatePaths += (Join-Path $env:CONDA_PREFIX "pythonw.exe")
    }

    $condaRoots = @(
        (Join-Path $env:USERPROFILE "miniconda3"),
        (Join-Path $env:USERPROFILE "anaconda3"),
        (Join-Path $env:ProgramData "miniconda3"),
        (Join-Path $env:ProgramData "anaconda3")
    )
    foreach ($root in $condaRoots) {
        foreach ($envName in @("taxamask", "antsleap")) {
            $candidatePaths += (Join-Path $root "envs\$envName\pythonw.exe")
        }
    }

    foreach ($candidate in $candidatePaths) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $pythonwCommand = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($pythonwCommand) {
        return $pythonwCommand.Source
    }

    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    throw "Cannot find pythonw.exe or python.exe. Create a Conda environment named 'taxamask', or set TAXAMASK_PYTHONW_EXE/TAXAMASK_PYTHON_EXE."
}

$pythonw = Find-TaxaMaskPythonw
Start-Process -FilePath $pythonw -ArgumentList @($main) -WorkingDirectory $repo -WindowStyle Hidden
