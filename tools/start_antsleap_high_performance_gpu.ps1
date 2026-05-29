$ErrorActionPreference = "Stop"

$env:QT_OPENGL = "desktop"
$env:__NV_PRIME_RENDER_OFFLOAD = "1"
$env:__GLX_VENDOR_LIBRARY_NAME = "nvidia"

$pythonw = "C:\Users\admin\anaconda3\envs\antsleap\pythonw.exe"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$main = Join-Path $repo "AntSleap\main.py"

Start-Process -FilePath $pythonw -ArgumentList @($main) -WorkingDirectory $repo -WindowStyle Hidden
