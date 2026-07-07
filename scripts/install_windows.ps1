param(
    [string]$Python = "",
    [switch]$AssumeYes,
    [string]$PythonInstallerVersion = "3.11.9",
    [string]$PythonInstallerUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Write-Info([string]$Message) {
    Write-Host "[*] $Message"
}

function Write-Warn([string]$Message) {
    Write-Warning $Message
}

function Confirm-Action([string]$Prompt) {
    if ($AssumeYes -or $env:IMR_PROXY_ASSUME_YES -eq "1") {
        return $true
    }

    $reply = Read-Host "$Prompt [y/N]"
    return $reply -match '^(y|yes)$'
}

function Invoke-NativeChecked([string]$Command, [string[]]$Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $Command $($Arguments -join ' ')"
    }
}

function Test-PythonCompatible([string]$Command, [string[]]$Arguments) {
    try {
        $allArgs = @($Arguments) + @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)")
        & $Command @allArgs *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Get-PythonCommand {
    if ($Python.Trim().Length -gt 0) {
        $parts = $Python.Trim().Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)
        $cmd = $parts[0]
        $args = @()
        if ($parts.Length -gt 1) {
            $args = $parts[1..($parts.Length - 1)]
        }
        if (Test-PythonCompatible -Command $cmd -Arguments $args) {
            return @{ Command = $cmd; Arguments = $args }
        }
        throw "The Python command supplied with -Python is not Python 3.11+: $Python"
    }

    $candidates = @(
        @{ Command = "py"; Arguments = @("-3.11") },
        @{ Command = "python"; Arguments = @() },
        @{ Command = "python3"; Arguments = @() }
    )

    foreach ($candidate in $candidates) {
        if (Test-PythonCompatible -Command $candidate.Command -Arguments $candidate.Arguments) {
            return $candidate
        }
    }

    $localPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
    if (Test-Path $localPython) {
        if (Test-PythonCompatible -Command $localPython -Arguments @()) {
            return @{ Command = $localPython; Arguments = @() }
        }
    }

    return $null
}

function Install-Python311 {
    if (-not (Confirm-Action "Python 3.11+ was not found. Do you want to download and install Python $PythonInstallerVersion from python.org now?")) {
        throw "Python 3.11+ is required. Install it manually or rerun with -AssumeYes."
    }

    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) "imr-proxy-python"
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    $installerPath = Join-Path $tempDir "python-$PythonInstallerVersion-amd64.exe"

    Write-Info "Downloading $PythonInstallerUrl"
    Invoke-WebRequest -Uri $PythonInstallerUrl -OutFile $installerPath -UseBasicParsing

    Write-Info "Starting Python installer for current user. This script does not change PowerShell execution policy."
    $installArgs = @(
        "/passive",
        "InstallAllUsers=0",
        "PrependPath=1",
        "Include_launcher=1",
        "Include_pip=1",
        "Include_test=0"
    )
    $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Python installer failed with exit code $($process.ExitCode)."
    }

    Write-Info "Python installer finished. If Python is not detected immediately, open a new PowerShell session."
}

function Invoke-Python([hashtable]$PythonCommand, [string[]]$Arguments) {
    & $PythonCommand.Command @($PythonCommand.Arguments + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $($PythonCommand.Command) $($PythonCommand.Arguments -join ' ') $($Arguments -join ' ')"
    }
}

Write-Info "Installing imr-proxy"
Write-Info "Project root: $ProjectRoot"

if (-not (Test-Path (Join-Path $ProjectRoot "pyproject.toml"))) {
    throw "pyproject.toml was not found at $ProjectRoot. Run this script from the extracted imr-proxy project, or keep the scripts directory inside the project root."
}

$legacyVenv = Join-Path $ScriptDir ".venv"
if (Test-Path $legacyVenv) {
    Write-Warn "A previous virtual environment exists inside scripts\.venv. It is not used anymore. You can delete it manually after this install succeeds: $legacyVenv"
}

$pythonCommand = Get-PythonCommand
if ($null -eq $pythonCommand) {
    Install-Python311
    $pythonCommand = Get-PythonCommand
}

if ($null -eq $pythonCommand) {
    throw "Python 3.11+ still was not found. Open a new PowerShell session or pass -Python with the full python.exe path."
}

$versionOutput = & $pythonCommand.Command @($pythonCommand.Arguments + @("--version"))
Write-Info "Using Python: $versionOutput"

Invoke-Python -PythonCommand $pythonCommand -Arguments @("-m", "venv", $VenvDir)
Invoke-NativeChecked -Command $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
Push-Location $ProjectRoot
try {
    Invoke-NativeChecked -Command $VenvPython -Arguments @("-m", "pip", "install", "-e", ".")
}
finally {
    Pop-Location
}

$CommandPath = Join-Path $VenvDir "Scripts\imr-proxy.exe"
Write-Info "Installed successfully."
Write-Info "Activate it with: cd `"$ProjectRoot`"; .\.venv\Scripts\Activate.ps1"
Write-Info "Check version with: imr-proxy --version"
Write-Info "Direct command without activation: `"$CommandPath`" --version"
Write-Info "This script does not change execution policy."
