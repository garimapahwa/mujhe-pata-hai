# Side Eye installer for Windows - https://garimapahwa.github.io/side-eye
#
#   Install / update (PowerShell):  irm https://garimapahwa.github.io/side-eye/install.ps1 | iex
#   Uninstall:                      $env:SIDEEYE_UNINSTALL=1; irm https://garimapahwa.github.io/side-eye/install.ps1 | iex
#
# No admin rights. Everything lives in your user folder:
#   %LOCALAPPDATA%\SideEye\        code, Python environment, your settings
#   Start menu "Side Eye" shortcut, and an entry in Startup apps (Start with Windows)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Invoke-WebRequest is very slow with the progress bar on

$Repo    = "garimapahwa/side-eye"
$Branch  = "main"
$AppName = "Side Eye"
$Support = Join-Path $env:LOCALAPPDATA "SideEye"
$Src     = Join-Path $Support "app"
$Venv    = Join-Path $Support "venv"
$PyW     = Join-Path $Venv "Scripts\pythonw.exe"
$Shortcut = Join-Path ([Environment]::GetFolderPath("Programs")) "$AppName.lnk"
$RunKey  = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

function Say($msg)  { Write-Host "> $msg" }
function Ok($msg)   { Write-Host "  $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "! $msg" -ForegroundColor Yellow }
function Die($msg)  { Write-Host "x $msg" -ForegroundColor Red; throw $msg }

function Stop-SideEye {
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*SideEye*tray.py*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

if ($env:SIDEEYE_UNINSTALL) {
    Remove-Item Env:\SIDEEYE_UNINSTALL
    Say "Removing $AppName..."
    Stop-SideEye
    Start-Sleep -Milliseconds 500
    Remove-ItemProperty -Path $RunKey -Name "SideEye" -ErrorAction SilentlyContinue
    Remove-Item $Shortcut -Force -ErrorAction SilentlyContinue
    Remove-Item $Support -Recurse -Force -ErrorAction SilentlyContinue
    Ok "Uninstalled."
    return
}

Write-Host ""
Write-Host "  $AppName" -ForegroundColor White
Write-Host "  your Hinglish voice focus buddy - powered by Sarvam AI" -ForegroundColor DarkGray
Write-Host ""

# ---------------------------------------------------------------- 1. Python 3.11+
function Find-Python {
    $candidates = @(
        @{ Exe = "py"; Args = @("-3.13") }, @{ Exe = "py"; Args = @("-3.12") }, @{ Exe = "py"; Args = @("-3.11") },
        @{ Exe = "python"; Args = @() }, @{ Exe = "python3"; Args = @() },
        @{ Exe = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"; Args = @() },
        @{ Exe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"; Args = @() },
        @{ Exe = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"; Args = @() }
    )
    foreach ($c in $candidates) {
        $exe = $c.Exe; $pyArgs = $c.Args
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        try {
            # the Microsoft Store "python" stub prints nothing useful, so check the version for real
            $out = @(& $exe @pyArgs -c "import sys; print(sys.version_info >= (3, 11)); print(sys.executable)" 2>$null)
            if ($out.Count -ge 2 -and $out[0] -eq "True") { return $out[1] }
        } catch { }
    }
    return $null
}

$Py = Find-Python
if (-not $Py) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Say "Installing Python 3.12 (one-time, about a minute)..."
        winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Null
        $Py = Find-Python
    }
    if (-not $Py) { Die "Python 3.11+ is needed. Install it from https://www.python.org/downloads/windows/ and run this command again." }
}
Ok "Python: $(& $Py --version 2>&1)"

# ---------------------------------------------------------------- 2. download the app (keep the user's .env on update)
$FirstInstall = -not (Test-Path $Src)
$HadStartup = $null -ne (Get-ItemProperty -Path $RunKey -Name "SideEye" -ErrorAction SilentlyContinue)
Stop-SideEye
Start-Sleep -Milliseconds 500
New-Item -ItemType Directory -Force -Path $Support | Out-Null
$SavedEnv = $null
if (Test-Path (Join-Path $Src ".env")) { $SavedEnv = [IO.File]::ReadAllText((Join-Path $Src ".env")) }
$Tmp = Join-Path ([IO.Path]::GetTempPath()) ("sideeye-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
try {
    if ($env:SIDEEYE_SOURCE) {  # local testing: install from a checkout instead of GitHub
        Say "Copying from $env:SIDEEYE_SOURCE..."
        Copy-Item $env:SIDEEYE_SOURCE (Join-Path $Tmp "src") -Recurse
    } else {
        Say "Downloading $AppName..."
        $zip = Join-Path $Tmp "src.zip"
        Invoke-WebRequest "https://github.com/$Repo/archive/refs/heads/$Branch.zip" -OutFile $zip -UseBasicParsing
        Expand-Archive $zip -DestinationPath $Tmp -Force
        Move-Item (Get-ChildItem $Tmp -Directory | Where-Object { $_.Name -like "*-$Branch" } | Select-Object -First 1).FullName (Join-Path $Tmp "src")
    }
    if (Test-Path $Src) { Remove-Item $Src -Recurse -Force }
    Move-Item (Join-Path $Tmp "src") $Src
} finally {
    Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue
}
if ($SavedEnv) { [IO.File]::WriteAllText((Join-Path $Src ".env"), $SavedEnv) }
Ok "Code in $Src"

# ---------------------------------------------------------------- 3. Python environment
Say "Setting up the Python environment (about a minute the first time)..."
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) { & $Py -m venv $Venv }
$VPy = Join-Path $Venv "Scripts\python.exe"
& $VPy -m pip install --quiet --disable-pip-version-check --upgrade pip | Out-Null
& $VPy -m pip install --quiet --disable-pip-version-check -r (Join-Path $Src "requirements.txt")
if ($LASTEXITCODE -ne 0) { Die "Installing dependencies failed (see the pip output above)." }
Ok "Dependencies installed"

# ---------------------------------------------------------------- 4. Sarvam API key
$EnvFile = Join-Path $Src ".env"
$HasKey = (Test-Path $EnvFile) -and ((Get-Content $EnvFile -Raw) -match "SARVAM_API_KEY=.+")
if (-not $HasKey) {
    Write-Host ""
    Write-Host "Sarvam AI API key " -NoNewline
    Write-Host "(free at https://dashboard.sarvam.ai - press Enter to add it later from the tray menu)" -ForegroundColor DarkGray
    $Key = ""
    try { $Key = (Read-Host "  Paste key").Trim() } catch { }
    if ($Key) {
        [IO.File]::WriteAllText($EnvFile, "SARVAM_API_KEY=$Key`n")  # no BOM, so python-dotenv reads it
        Ok "Key saved (only on this PC)"
    } else {
        Warn "No key yet - the app will ask for it when you switch it on."
    }
}

# ---------------------------------------------------------------- 5. Start menu shortcut + Start with Windows
$Tray = Join-Path $Src "tray.py"
$Shell = New-Object -ComObject WScript.Shell
$Lnk = $Shell.CreateShortcut($Shortcut)
$Lnk.TargetPath = $PyW
$Lnk.Arguments = "`"$Tray`""
$Lnk.WorkingDirectory = $Src
$Lnk.Description = "Side Eye - your Hinglish voice focus buddy"
$Lnk.Save()
if ($FirstInstall -or $HadStartup) {  # keep the user's "Start with Windows" choice on update
    Set-ItemProperty -Path $RunKey -Name "SideEye" -Value "`"$PyW`" `"$Tray`""
}
Ok "Added $AppName to the Start menu"

# ---------------------------------------------------------------- 6. start it
Start-Process -FilePath $PyW -ArgumentList "`"$Tray`"" -WorkingDirectory $Src
Write-Host ""
Write-Host "  Ho gaya!" -ForegroundColor Green -NoNewline
Write-Host "  Click the eye in your system tray (by the clock; it may be under the ^ arrow)."
Write-Host "  Allow the microphone if Windows asks. Run this command again to update." -ForegroundColor DarkGray
Write-Host ""
