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

function Add-CondaEnvListCandidates {
    param([string[]] $EnvNamePatterns = @("taxamask*"))

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
                if ($EnvNamePatterns | Where-Object { $leaf -like $_ }) {
                    $script:candidates += (Join-Path $envPath "pythonw.exe")
                    $script:candidates += (Join-Path $envPath "python.exe")
                }
            }
        } catch {
            continue
        }
    }
}

Add-CondaEnvListCandidates

$candidates += (Join-Path $env:USERPROFILE "miniconda3\envs\taxamask\pythonw.exe")
$candidates += (Join-Path $env:USERPROFILE "anaconda3\envs\taxamask\pythonw.exe")
$candidates += (Join-Path $env:USERPROFILE "miniforge3\envs\taxamask\pythonw.exe")
$candidates += (Join-Path $env:USERPROFILE "mambaforge\envs\taxamask\pythonw.exe")
$candidates += (Join-Path $env:ProgramData "miniconda3\envs\taxamask\pythonw.exe")
$candidates += (Join-Path $env:ProgramData "anaconda3\envs\taxamask\pythonw.exe")
$candidates += (Join-Path $env:ProgramData "miniforge3\envs\taxamask\pythonw.exe")
$candidates += (Join-Path $env:ProgramData "mambaforge\envs\taxamask\pythonw.exe")

foreach ($drive in @("C", "D", "E", "F", "G", "H")) {
    foreach ($rootName in @("miniconda3", "anaconda3", "miniforge3", "mambaforge", "conda", "Anaconda", "Miniconda")) {
        $envRoot = Join-Path "${drive}:\" "$rootName\envs"
        if (Test-Path -LiteralPath $envRoot) {
            Get-ChildItem -LiteralPath $envRoot -Directory -Filter "taxamask*" -ErrorAction SilentlyContinue | ForEach-Object {
                $candidates += (Join-Path $_.FullName "pythonw.exe")
                $candidates += (Join-Path $_.FullName "python.exe")
            }
        }
    }
}

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
