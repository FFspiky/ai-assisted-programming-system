param(
    [ValidateSet('setup', 'start')][string]$Action,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$QuickstartArgs
)

$ErrorActionPreference = 'Stop'

function Find-CodeLabPython {
    $candidates = @((Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'))
    foreach ($name in @('python3', 'python', 'python3.13', 'python3.12', 'python3.11')) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue
        if ($command) { $candidates += $command.Source }
    }
    # Discover installations even when this terminal has an old PATH.
    foreach ($base in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore')) {
        foreach ($key in @(Get-ChildItem $base -ErrorAction SilentlyContinue)) {
            $location = Get-ItemProperty "$($key.PSPath)\InstallPath" -ErrorAction SilentlyContinue
            if ($location -and $location.'(default)') {
                $candidates += Join-Path $location.'(default)' 'python.exe'
            }
        }
    }
    # Installed Store runtimes have a package-specific alias; the bare alias may only open the Store.
    $storeAliases = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'
    foreach ($package in @(Get-ChildItem -LiteralPath $storeAliases -Directory -Filter 'PythonSoftwareFoundation.Python.*' -ErrorAction SilentlyContinue)) {
        $candidates += Join-Path $package.FullName 'python.exe'
    }
    $candidates += Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        # Do not activate the Microsoft Store alias while probing for Python.
        if ((Split-Path -Parent $candidate) -eq $storeAliases -or !(Test-Path -LiteralPath $candidate)) { continue }
        try {
            $resolved = & $candidate -c 'import sys; sys.exit(1) if sys.version_info < (3,11) else print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved) { return [string]@($resolved)[-1] }
        } catch { continue }
    }
    return $null
}

function Confirm-CodeLabPython {
    if ([Console]::IsInputRedirected) { throw 'Python 3.11+ was not found. Run setup interactively to install it.' }
    $answer = Read-Host 'Python 3.11+ was not found. Download and install Python 3.13.17 from python.org? [y/N]'
    if ($answer -notmatch '^(?i:y|yes)$') { throw 'Python installation skipped. Run setup again when ready.' }
}

function Install-CodeLabPython {
    Confirm-CodeLabPython
    $architecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
    switch ($architecture) {
        'AMD64' { $suffix = 'amd64'; $hash = '5da012101ba2e17113a9a1cd901e9ce1441086f2b7ecb5de06ec94163899a190' }
        'ARM64' { $suffix = 'arm64'; $hash = '3089a1977c32b26f5078e5a7d0285b7a861b8c96250c5dac3b6af59fbe9e9a75' }
        default { throw 'A 64-bit Windows system is required.' }
    }
    $installer = Join-Path ([IO.Path]::GetTempPath()) ('codelab-python-' + [guid]::NewGuid().ToString('N') + '.exe')
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Write-Host 'Downloading the official Python installer...'
        Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/3.13.17/python-3.13.17-$suffix.exe" -OutFile $installer
        if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne $hash) {
            throw 'Python installer checksum mismatch. Nothing was installed; retry the download.'
        }
        $process = Start-Process -FilePath $installer -ArgumentList @('/passive', '/norestart', 'InstallAllUsers=0', 'PrependPath=1', 'Include_test=0', 'InstallLauncherAllUsers=0') -PassThru -Wait
        if ($process.ExitCode -eq 3010 -or $process.ExitCode -eq 1641) {
            throw 'Python requires a restart. Restart Windows, then run setup-windows.cmd again.'
        }
        if ($process.ExitCode -ne 0) { throw "Python installation did not finish (exit $($process.ExitCode)). Run setup again." }
    } finally {
        if (Test-Path -LiteralPath $installer) { Remove-Item -LiteralPath $installer -Force }
    }
}

function Invoke-CodeLabLauncher {
    Set-Location -LiteralPath (Join-Path $PSScriptRoot '..')
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $python = Find-CodeLabPython
    if (!$python -and $Action -eq 'setup' -and '--skip-prerequisites' -notin $QuickstartArgs) {
        Install-CodeLabPython
        $python = Find-CodeLabPython
    }
    if (!$python) { throw 'Python 3.11+ was not found. Run setup-windows.cmd to install it, or install from https://www.python.org/downloads/.' }
    & $python -B (Join-Path $PSScriptRoot 'quickstart.py') $Action @QuickstartArgs | Out-Host
    return $LASTEXITCODE
}

# Dot-sourcing exposes functions for tests without running installers.
if ($MyInvocation.InvocationName -ne '.') {
    try { exit (Invoke-CodeLabLauncher) }
    catch { Write-Host "Setup did not finish: $($_.Exception.Message)"; exit 1 }
}
