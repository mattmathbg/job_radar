# ──────────────────────────────────────────────────────────────────────────────
# JobRadar — Windows Smart Setup (PowerShell)
# Checks what exists before downloading anything. Safe to re-run.
# Run: .\setup.ps1   OR   powershell -ExecutionPolicy Bypass -File setup.ps1
# ──────────────────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir   = Join-Path $ScriptDir ".venv"
$BinDir    = Join-Path $ScriptDir "bin"
$ModelDir  = Join-Path $ScriptDir "models"
$ModelFile = Join-Path $ModelDir "qwen3-1.7b-q4_k_m.gguf"

function Ok   { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Skip { param($msg) Write-Host "  [>>] $msg (already exists)" -ForegroundColor Yellow }
function Warn { param($msg) Write-Host "  [!!] $msg" -ForegroundColor Yellow }
function Fail { param($msg) Write-Host "  [XX] $msg" -ForegroundColor Red }
function Info { param($msg) Write-Host $msg -ForegroundColor Cyan }

# ── Step 1: Check Python ────────────────────────────────────────────────────
Info "`n-- Step 1/5: Python --"
$pyCmd = $null

# Try py launcher first (standard Windows Python)
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $pyCmd = "py"
} elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    # Check if it's Python 3
    $ver = & python -c "import sys; print(sys.version_info.major)" 2>$null
    if ($ver -eq "3") { $pyCmd = "python" }
}

if ($pyCmd) {
    $pyVer = & $pyCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    $parts = $pyVer -split "\."

    if ($parts.Count -lt 2) {
        Fail "Could not detect Python version"
        exit 1
    }

    if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 9) {
        Ok "Python $pyVer found"
    } else {
        Fail "Python 3.9+ required (found $pyVer)"
        exit 1
    }
} else {
    Fail "Python not found. Install from https://python.org (check 'Add to PATH')"
    exit 1
}

# ── Step 2: Python venv + pip packages ──────────────────────────────────────
Info "`n-- Step 2/5: Python packages --"

if (Test-Path $VenvDir) {
    Skip "Virtual environment at $VenvDir"
} else {
    Info "  Creating virtual environment..."
    & $pyCmd -m venv $VenvDir
    Ok "Virtual environment created"
}

# Activate venv in the current PowerShell session
$activateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    . $activateScript
} else {
    Fail "Activation script not found: $activateScript"
    exit 1
}

# Use the venv Python consistently
$venvPython = Join-Path $VenvDir "Scripts\python.exe"

# Check core packages
$corePkgs = @("rich", "yaml", "requests", "bs4", "pytest")
$missingCore = @()
foreach ($pkg in $corePkgs) {
    $modName = if ($pkg -eq "bs4") { "bs4" } elseif ($pkg -eq "yaml") { "yaml" } else { $pkg }
    & $venvPython -c "import $modName" 2>$null
    if ($LASTEXITCODE -ne 0) { $missingCore += $pkg }
}

if ($missingCore.Count -eq 0) {
    Skip "Core Python packages already installed"
} else {
    Info "  Installing $($missingCore.Count) missing package(s)..."
    & $venvPython -m pip install -q -r (Join-Path $ScriptDir "requirements.txt")
    Ok "Core packages installed"
}

# Dashboard packages
$dashPkgs = @("fastapi", "uvicorn", "pydantic")
$missingDash = @()
foreach ($pkg in $dashPkgs) {
    & $venvPython -c "import $pkg" 2>$null
    if ($LASTEXITCODE -ne 0) { $missingDash += $pkg }
}

if ($missingDash.Count -eq 0) {
    Skip "Dashboard packages already installed"
} else {
    Info "  Installing $($missingDash.Count) missing dashboard package(s)..."
    & $venvPython -m pip install -q -r (Join-Path $ScriptDir "dashboard\requirements.txt")
    Ok "Dashboard packages installed"
}

# ── Step 3: llama-server ────────────────────────────────────────────────────
Info "`n-- Step 3/5: llama-server --"
if (-not (Test-Path $BinDir)) { New-Item -ItemType Directory -Path $BinDir | Out-Null }

$llamaExe = Join-Path $BinDir "llama-server.exe"

# Check common locations
$llamaFound = $false
$candidates = @(
    $llamaExe,
    (Join-Path $env:LOCALAPPDATA "Programs\llama.cpp\llama-server.exe"),
    (Join-Path $env:ProgramFiles "llama.cpp\llama-server.exe"),
    (Join-Path $env:LOCALAPPDATA "ollama\llama-server.exe")
)

foreach ($c in $candidates) {
    if (Test-Path $c) {
        $script:llamaBin = $c
        $llamaFound = $true
        Skip "llama-server found at $c"
        break
    }
}

if (-not $llamaFound) {
    if (Get-Command "llama-server" -ErrorAction SilentlyContinue) {
        $script:llamaBin = (Get-Command "llama-server").Source
        $llamaFound = $true
        Skip "llama-server found at $($script:llamaBin)"
    }
}

if (-not $llamaFound) {
    Info "  Downloading llama.cpp for Windows x64..."

    # Get latest release tag
    $latestTag = ""
    try {
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest" -TimeoutSec 10
        $latestTag = $release.tag_name
    } catch {
        Warn "Could not reach GitHub API"
    }

    if ($latestTag) {
        Info "  Latest release: $latestTag"
        $downloaded = $false

        foreach ($pattern in @("llama-server-windows-x64.zip", "llama-win-x64.zip")) {
            $dlUrl = "https://github.com/ggml-org/llama.cpp/releases/download/$latestTag/$pattern"
            $tmpZip = Join-Path $env:TEMP "llama.zip"
            try {
                Invoke-WebRequest -Uri $dlUrl -OutFile $tmpZip -TimeoutSec 120 -UseBasicParsing
                $downloaded = $true
                break
            } catch {
                # try next pattern
            }
        }

        if ($downloaded) {
            Info "  Extracting..."
            $tmpExtract = Join-Path $env:TEMP "llama_extract"
            if (Test-Path $tmpExtract) {
                Remove-Item $tmpExtract -Recurse -Force -ErrorAction SilentlyContinue
            }
            Expand-Archive -Path $tmpZip -DestinationPath $tmpExtract -Force
            $found = Get-ChildItem -Path $tmpExtract -Recurse -Filter "llama-server.exe" | Select-Object -First 1
            if ($found) {
                Copy-Item $found.FullName $llamaExe -Force
                $script:llamaBin = $llamaExe
                Ok "llama-server installed at $llamaExe"
            } else {
                # Copy all llama-*.exe
                Get-ChildItem -Path $tmpExtract -Recurse -Filter "llama-*.exe" | ForEach-Object {
                    Copy-Item $_.FullName $BinDir -Force
                }
                if (Test-Path $llamaExe) {
                    $script:llamaBin = $llamaExe
                    Ok "llama-server installed at $llamaExe"
                } else {
                    Warn "Download succeeded but llama-server.exe not found in archive"
                }
            }
            Remove-Item $tmpExtract -Recurse -Force -ErrorAction SilentlyContinue
            Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue
        } else {
            Warn "Could not download llama.cpp from GitHub releases"
        }
    }

    if (-not (Test-Path $llamaExe)) {
        Warn "Install llama.cpp manually:"
        Warn "  https://github.com/ggml-org/llama.cpp/releases"
        Warn "  Or install Ollama: https://ollama.com"
    }
}

# ── Step 4: LLM Model ──────────────────────────────────────────────────────
Info "`n-- Step 4/5: LLM Model --"
if (-not (Test-Path $ModelDir)) { New-Item -ItemType Directory -Path $ModelDir | Out-Null }

$modelExists = Get-ChildItem -Path $ModelDir -Filter "*.gguf" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($modelExists) {
    Skip "Model found: $($modelExists.Name)"
} else {
    Info "  Downloading qwen3-1.7b Q4_K_M (~1.1 GB)..."
    Info "  This is a small, fast model - good for CPU inference"

    $modelUrl = "https://huggingface.co/unsloth/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf"
    $modelPart = "$ModelFile.part"

    try {
        # Use WebClient for progress on large files
        $wc = New-Object System.Net.WebClient
        try {
            $wc.DownloadFile($modelUrl, $modelPart)
        } finally {
            $wc.Dispose()
        }

        Move-Item $modelPart $ModelFile -Force
        $size = (Get-Item $ModelFile).Length / 1GB
        Ok "Model saved: $ModelFile ($([math]::Round($size, 1)) GB)"
    } catch {
        Remove-Item $modelPart -Force -ErrorAction SilentlyContinue
        Fail "Model download failed: $_"
        Warn "Download manually from:"
        Warn "  $modelUrl"
        Warn "  Save to: $ModelDir\"
    }
}

# ── Step 5: Profile config ──────────────────────────────────────────────────
Info "`n-- Step 5/5: Configuration --"
$profilePath = Join-Path $ScriptDir "profile.yaml"

if (Test-Path $profilePath) {
    Skip "profile.yaml exists"
} else {
    @"
# JobRadar Profile - edit this with your details
name: "Your Name"
title: "Software Engineer"
experience_years: 3
skills:
  - Python
  - JavaScript
  - Docker
desired_roles:
  - Backend Engineer
  - Full Stack Developer
salary_min: 80000
salary_max: 150000
location_preference: "Remote"
remote_ok: true
industries:
  - Technology
  - SaaS
"@ | Out-File -FilePath $profilePath -Encoding utf8
    Warn "Created default profile.yaml - edit it with your real details!"
}

$companiesPath = Join-Path $ScriptDir "companies.yaml"
if (Test-Path $companiesPath) {
    Skip "companies.yaml exists"
} else {
    Warn "companies.yaml not found - using defaults in jobradar/sources/"
}

# ── Done ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  JobRadar is ready!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Quick start:"
Write-Host "    cd $ScriptDir"
Write-Host "    . .venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "  CLI search (no AI - fast):"
Write-Host "    python -m jobradar -q `"python developer`" --no-ai"
Write-Host ""
Write-Host "  CLI search (with AI scoring):"
Write-Host "    python -m jobradar -q `"python developer`" -p profile.yaml"
Write-Host ""
Write-Host "  Web dashboard:"
Write-Host "    Set-Location dashboard; python -m uvicorn app:app --port 3000"
Write-Host "    Open http://localhost:3000"
Write-Host ""
