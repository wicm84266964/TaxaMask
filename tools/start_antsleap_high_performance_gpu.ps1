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

    $condaCommands = @()
    foreach ($commandName in @("conda.bat", "conda.exe")) {
        Get-Command $commandName -All -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandType -eq "Application" -and $_.Source } |
            ForEach-Object { $condaCommands += $_.Source }
    }

    $condaRoots = @(
        (Join-Path $env:USERPROFILE "miniconda3"),
        (Join-Path $env:USERPROFILE "anaconda3"),
        (Join-Path $env:USERPROFILE "miniforge3"),
        (Join-Path $env:USERPROFILE "mambaforge"),
        (Join-Path $env:ProgramData "miniconda3"),
        (Join-Path $env:ProgramData "anaconda3"),
        (Join-Path $env:ProgramData "miniforge3"),
        (Join-Path $env:ProgramData "mambaforge")
    )
    foreach ($drive in @("C", "D", "E", "F", "G", "H")) {
        foreach ($rootName in @("miniconda3", "anaconda3", "miniforge3", "mambaforge", "conda", "Anaconda", "Miniconda")) {
            $condaRoots += (Join-Path "${drive}:\" $rootName)
        }
    }
    foreach ($root in $condaRoots) {
        $condaBat = Join-Path $root "condabin\conda.bat"
        if (Test-Path -LiteralPath $condaBat) {
            $condaCommands += $condaBat
        }
    }
    foreach ($conda in ($condaCommands | Where-Object { $_ } | Select-Object -Unique)) {
        try {
            $raw = & $conda env list --json 2>$null
            if ($LASTEXITCODE -ne 0 -or -not $raw) {
                continue
            }
            $envs = ($raw | ConvertFrom-Json).envs
            foreach ($envPath in $envs) {
                $leaf = Split-Path -Leaf $envPath
                if ($leaf -like "taxamask*" -or $leaf -like "antsleap*") {
                    $candidatePaths += (Join-Path $envPath "pythonw.exe")
                    $candidatePaths += (Join-Path $envPath "python.exe")
                }
            }
        } catch {
            continue
        }
    }
    foreach ($root in $condaRoots) {
        foreach ($envName in @("taxamask", "antsleap")) {
            $candidatePaths += (Join-Path $root "envs\$envName\pythonw.exe")
        }
        $envRoot = Join-Path $root "envs"
        if (Test-Path -LiteralPath $envRoot) {
            Get-ChildItem -LiteralPath $envRoot -Directory -Filter "taxamask*" -ErrorAction SilentlyContinue | ForEach-Object {
                $candidatePaths += (Join-Path $_.FullName "pythonw.exe")
                $candidatePaths += (Join-Path $_.FullName "python.exe")
            }
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
