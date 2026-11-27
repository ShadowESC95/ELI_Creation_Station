# Adapted from ELI_Legal: packaging/windows/build.ps1 @ 3b05ccd88f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes.
# Build the Windows installer: PyInstaller, then Inno Setup.
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
#
# Needs Python 3.10 or newer and Inno Setup 6 (https://jrsoftware.org/isinfo.php). To sign the
# programs and the installer, set ELI_CREATION_SIGN_CMD to a command taking the file as its last
# argument (for example a signtool invocation); unsigned builds trigger a SmartScreen warning.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root

$Py = if ($env:PYTHON) { $env:PYTHON } elseif (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
& $Py -m pip install --quiet -e ".[all,build]"
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
$env:ELI_CREATION_VERSION = (& $Py -c "import eli_creation; print(eli_creation.__version__)").Trim()

& $Py scripts\third_party_notices.py
& $Py -m PyInstaller packaging\pyinstaller\eli_creation.spec --noconfirm --distpath build\dist --workpath build\work --log-level WARN
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
& "build\dist\eli-creation\eli-creation.exe" --help | Out-Null
if ($LASTEXITCODE -ne 0) { throw "the frozen program does not start" }

function Sign($File) {
    if ($env:ELI_CREATION_SIGN_CMD) {
        Invoke-Expression "$($env:ELI_CREATION_SIGN_CMD) `"$File`""
        if ($LASTEXITCODE -ne 0) { throw "signing failed: $File" }
    }
}
Sign "build\dist\eli-creation\eli-creation.exe"
Sign "build\dist\eli-creation\eli-creation-gui.exe"

$Iscc = @(
    (Get-Command iscc.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $Iscc) { throw "Inno Setup 6 was not found. Install it, then run this script again." }

New-Item -ItemType Directory -Force -Path dist\installers | Out-Null
& $Iscc /Qp packaging\windows\eli_creation.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
$Setup = "dist\installers\ELI_Creation_Station-$($env:ELI_CREATION_VERSION)-windows-x64-setup.exe"
Sign $Setup
$Hash = (Get-FileHash $Setup -Algorithm SHA256).Hash.ToLower()
"$Hash  $(Split-Path $Setup -Leaf)" | Out-File -Encoding ascii "dist\installers\SHA256SUMS-windows"
Write-Host "Built $Setup"
Write-Host "SHA-256 $Hash"
