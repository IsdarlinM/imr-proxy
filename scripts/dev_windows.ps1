param(
    [string]$Python = "py -3.11"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Invoke-NativeChecked([string]$Command, [string[]]$Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $Command $($Arguments -join ' ')"
    }
}

$parts = $Python.Trim().Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)
$cmd = $parts[0]
$args = @()
if ($parts.Length -gt 1) { $args = $parts[1..($parts.Length - 1)] }

Push-Location $ProjectRoot
try {
    & $cmd @($args + @("-m", "venv", $VenvDir))
    if ($LASTEXITCODE -ne 0) { throw "Could not create virtual environment." }
    Invoke-NativeChecked -Command $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
    Invoke-NativeChecked -Command $VenvPython -Arguments @("-m", "pip", "install", "-e", ".[dev]")
    Invoke-NativeChecked -Command $VenvPython -Arguments @("-m", "pytest")
}
finally {
    Pop-Location
}
