[CmdletBinding()]
param(
    [string]$SourceRepo = "",
    [string]$ReleaseRepo = "C:\saveproject\LBJ-workspace\open-source\TaxaMask",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceRepo)) {
    $SourceRepo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string]$Repo,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $output = @(& git -C $Repo @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed in $Repo`n$($output -join "`n")"
    }
    return $output
}

function Resolve-RepositoryRoot {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $resolved -PathType Container)) {
        throw "Repository directory does not exist: $resolved"
    }
    $root = (Invoke-Git -Repo $resolved -Arguments @("rev-parse", "--show-toplevel") | Select-Object -First 1).Trim()
    return [System.IO.Path]::GetFullPath($root)
}

function Get-TrackedFileMap {
    param([Parameter(Mandatory = $true)][string]$Repo)

    $map = @{}
    foreach ($line in Invoke-Git -Repo $Repo -Arguments @("-c", "core.quotepath=false", "ls-files", "-s")) {
        $tabIndex = $line.IndexOf("`t")
        if ($tabIndex -lt 0) {
            throw "Unexpected git ls-files output: $line"
        }
        $metadata = @($line.Substring(0, $tabIndex) -split '\s+')
        if ($metadata.Count -lt 3) {
            throw "Unexpected git index metadata: $line"
        }
        $file = $line.Substring($tabIndex + 1).Replace("\", "/")
        $map[$file] = "$($metadata[0]):$($metadata[1])"
    }
    return $map
}

function Assert-CleanWorktree {
    param(
        [Parameter(Mandatory = $true)][string]$Repo,
        [Parameter(Mandatory = $true)][string]$Role
    )

    $status = @(Invoke-Git -Repo $Repo -Arguments @("status", "--porcelain=v1", "--untracked-files=all"))
    if ($status.Count -gt 0) {
        throw "$Role worktree must be clean before synchronization:`n$($status -join "`n")"
    }
}

function Assert-PublicFileSet {
    param(
        [Parameter(Mandatory = $true)][string]$Repo,
        [Parameter(Mandatory = $true)][string[]]$Files
    )

    $riskPatterns = @(
        '(?i)(^|/)\.lab-agent(/|$)',
        '(?i)(^|/)TaxaMask_outputs(/|$)',
        '(?i)(^|/)(private_docs|\.tmp_validation)(/|$)',
        '(?i)\.(db|sqlite|sqlite3|pt|pth|ckpt|onnx|tif|tiff|pdf|h5|hdf5|npy|npz|pkl|joblib|pem|pfx|p12)$',
        '(?i)(^|/)(api_runtime_settings|credentials|secrets?|tokens?)\.json$'
    )
    $riskyFiles = @(
        foreach ($file in $Files) {
            $blockedEnvironmentFile = (
                $file -match '(?i)(^|/)\.env(\..+)?$' -and
                $file -notmatch '(?i)(^|/)\.env\.(example|sample|template)$'
            )
            if ($blockedEnvironmentFile -or ($riskPatterns | Where-Object { $file -match $_ })) {
                $file
            }
        }
    )
    if ($riskyFiles.Count -gt 0) {
        throw "Tracked files include blocked public-release paths:`n$($riskyFiles -join "`n")"
    }

    $symlinks = @(
        Invoke-Git -Repo $Repo -Arguments @("-c", "core.quotepath=false", "ls-files", "-s") |
            Where-Object { $_ -match '^120000\s' }
    )
    if ($symlinks.Count -gt 0) {
        throw "Symlinks require manual release review and are not copied automatically:`n$($symlinks -join "`n")"
    }

    $textExtensions = @{}
    foreach ($value in @(
        ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".json", ".md", ".txt",
        ".yml", ".yaml", ".toml", ".ini", ".cfg", ".ps1", ".cmd", ".bat", ".sh",
        ".html", ".css", ".xml", ".csv", ".cff", ".gitignore", ".gitattributes"
    )) {
        $textExtensions[$value] = $true
    }
    $secretPatterns = @(
        '(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}',
        '(?<![A-Za-z0-9])ghp_[A-Za-z0-9]{20,}',
        'github_pat_[A-Za-z0-9_]{20,}',
        'AKIA[0-9A-Z]{16}',
        'AIza[0-9A-Za-z_-]{30,}',
        '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'
    )
    $secretHits = [System.Collections.Generic.List[string]]::new()
    foreach ($file in $Files) {
        $extension = [System.IO.Path]::GetExtension($file)
        $leaf = [System.IO.Path]::GetFileName($file)
        if (-not $textExtensions.ContainsKey($extension) -and
            -not $textExtensions.ContainsKey($leaf) -and
            $leaf -notmatch '(?i)^\.env\.(example|sample|template)$') {
            continue
        }
        $path = Join-Path $Repo $file
        $content = [System.IO.File]::ReadAllText($path)
        foreach ($pattern in $secretPatterns) {
            if ($content -match $pattern) {
                $secretHits.Add($file)
                break
            }
        }
    }
    if ($secretHits.Count -gt 0) {
        throw "Possible secrets found in tracked public-release files:`n$($secretHits -join "`n")"
    }
}

function Assert-ChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd("\")
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($fullRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes release repository: $fullPath"
    }
    return $fullPath
}

$source = Resolve-RepositoryRoot -Path $SourceRepo
$release = Resolve-RepositoryRoot -Path $ReleaseRepo
if ($source -eq $release) {
    throw "Source and release repositories must be different directories."
}

$sourceBranch = (Invoke-Git -Repo $source -Arguments @("branch", "--show-current") | Select-Object -First 1).Trim()
$releaseBranch = (Invoke-Git -Repo $release -Arguments @("branch", "--show-current") | Select-Object -First 1).Trim()
if ($sourceBranch -ne "main") {
    throw "Development repository must be on main, found: $sourceBranch"
}
if ($releaseBranch -ne "main") {
    throw "Public release repository must be on main, found: $releaseBranch"
}

$sourceRemotes = @(Invoke-Git -Repo $source -Arguments @("remote"))
if ($sourceRemotes -contains "origin") {
    throw "Development repository must not have a GitHub origin remote."
}
$releaseOrigin = (Invoke-Git -Repo $release -Arguments @("remote", "get-url", "origin") | Select-Object -First 1).Trim()
if ($releaseOrigin -ne "https://github.com/wicm84266964/TaxaMask.git") {
    throw "Unexpected public release origin: $releaseOrigin"
}

Assert-CleanWorktree -Repo $source -Role "Development"
Assert-CleanWorktree -Repo $release -Role "Public release"

$sourceMap = Get-TrackedFileMap -Repo $source
$releaseMap = Get-TrackedFileMap -Repo $release
$sourceFiles = @($sourceMap.Keys | Sort-Object)
$releaseFiles = @($releaseMap.Keys | Sort-Object)
Assert-PublicFileSet -Repo $source -Files $sourceFiles

$added = @($sourceFiles | Where-Object { -not $releaseMap.ContainsKey($_) })
$deleted = @($releaseFiles | Where-Object { -not $sourceMap.ContainsKey($_) })
$modified = @(
    foreach ($file in $sourceFiles) {
        if (-not $releaseMap.ContainsKey($file)) {
            continue
        }
        if ($sourceMap[$file] -ne $releaseMap[$file]) {
            $file
        }
    }
)
$modified = @($modified | Sort-Object)

$sourceCommit = (Invoke-Git -Repo $source -Arguments @("rev-parse", "HEAD") | Select-Object -First 1).Trim()
$releaseCommit = (Invoke-Git -Repo $release -Arguments @("rev-parse", "HEAD") | Select-Object -First 1).Trim()
Write-Host "Development: $sourceCommit"
Write-Host "Public release: $releaseCommit"
Write-Host "Tracked allowlist: $($sourceFiles.Count) files"
Write-Host "Changes: add=$($added.Count), modify=$($modified.Count), delete=$($deleted.Count)"

foreach ($file in $added) { Write-Host "ADD     $file" }
foreach ($file in $modified) { Write-Host "MODIFY  $file" }
foreach ($file in $deleted) { Write-Host "DELETE  $file" }

if (-not $Apply) {
    Write-Host "Preview only. Re-run with -Apply after reviewing the list."
    exit 0
}

foreach ($file in @($added + $modified)) {
    $sourcePath = Join-Path $source $file
    $releasePath = Assert-ChildPath -Root $release -Path (Join-Path $release $file)
    $parent = Split-Path -Parent $releasePath
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Copy-Item -LiteralPath $sourcePath -Destination $releasePath -Force
}
foreach ($file in $deleted) {
    $releasePath = Assert-ChildPath -Root $release -Path (Join-Path $release $file)
    if (Test-Path -LiteralPath $releasePath -PathType Leaf) {
        Remove-Item -LiteralPath $releasePath -Force
    }
}

$diffCheck = @(Invoke-Git -Repo $release -Arguments @("-c", "core.safecrlf=false", "diff", "--check"))
if ($diffCheck.Count -gt 0) {
    throw "git diff --check failed after synchronization:`n$($diffCheck -join "`n")"
}

Write-Host "Synchronization applied. Nothing was staged, committed, tagged, or pushed."
Write-Host "Review in: $release"
& git -C $release status --short
