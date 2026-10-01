[CmdletBinding()]
param(
    [string]$PackageName = "自媒体一键分发",
    [string]$PythonVersion = "3.12.3",
    [switch]$SkipFrontendBuild,
    [switch]$SkipRuntimeInstall
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-ChildPath {
    param(
        [string]$Child,
        [string]$Parent
    )

    $childFull = [System.IO.Path]::GetFullPath($Child)
    $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\') + '\'
    if (-not $childFull.StartsWith($parentFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside expected folder: $childFull"
    }
}

function Copy-CleanDirectory {
    param(
        [string]$Source,
        [string]$Destination
    )

    $sourceFull = (Resolve-Path -LiteralPath $Source).Path
    $prefix = $sourceFull.TrimEnd('\') + '\'
    $excludeDirs = @('__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'node_modules', '.vite')
    $excludeFiles = @('*.pyc', 'account.json', '*cookie*.json', '*token*.json', '*.log')

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Get-ChildItem -LiteralPath $sourceFull -Recurse -Force -File | ForEach-Object {
        $relative = $_.FullName.Substring($prefix.Length)
        $segments = $relative -split '[\\/]'
        foreach ($segment in $segments) {
            if ($excludeDirs -contains $segment) {
                return
            }
        }
        foreach ($pattern in $excludeFiles) {
            if ($_.Name -like $pattern) {
                return
            }
        }

        $target = Join-Path $Destination $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
}

function Install-PortablePython {
    param(
        [string]$RuntimePythonDir,
        [string]$CacheDir,
        [string]$Version
    )

    New-Item -ItemType Directory -Force -Path $RuntimePythonDir | Out-Null
    New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null

    $pythonZip = Join-Path $CacheDir "python-$Version-embed-amd64.zip"
    $pythonUrl = "https://www.python.org/ftp/python/$Version/python-$Version-embed-amd64.zip"
    if (-not (Test-Path -LiteralPath $pythonZip)) {
        Write-Step "Downloading portable Python $Version"
        Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonZip
    }

    Write-Step "Extracting portable Python"
    Expand-Archive -LiteralPath $pythonZip -DestinationPath $RuntimePythonDir -Force

    $pthFile = Get-ChildItem -LiteralPath $RuntimePythonDir -Filter "python*._pth" | Select-Object -First 1
    if (-not $pthFile) {
        throw "Cannot find Python ._pth file in $RuntimePythonDir"
    }

    $pthContent = Get-Content -LiteralPath $pthFile.FullName | ForEach-Object {
        if ($_ -eq "#import site") { "import site" } else { $_ }
    }
    foreach ($extraPath in @("..\..", "..\..\uploader", "..\..\myUtils", "..\..\utils")) {
        if ($pthContent -notcontains $extraPath) {
            $pthContent = @($extraPath) + $pthContent
        }
    }
    if ($pthContent -notcontains "import site") {
        $pthContent += "import site"
    }
    Set-Content -LiteralPath $pthFile.FullName -Value $pthContent -Encoding ASCII

    $pythonExe = Join-Path $RuntimePythonDir "python.exe"
    $getPip = Join-Path $CacheDir "get-pip.py"
    if (-not (Test-Path -LiteralPath $getPip)) {
        Write-Step "Downloading pip bootstrap"
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip
    }

    Write-Step "Installing pip into portable Python"
    & $pythonExe $getPip --no-warn-script-location 2>&1 | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "pip bootstrap failed"
    }

    return $pythonExe
}

function Install-BundledChromium {
    param(
        [string]$PythonExe,
        [string]$Destination
    )

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $pythonRoot = Split-Path -Parent $PythonExe
    $browsersJson = Join-Path $pythonRoot "Lib\site-packages\playwright\driver\package\browsers.json"
    $browserSpec = (Get-Content -Raw -LiteralPath $browsersJson | ConvertFrom-Json).browsers
    $chromiumRevision = ($browserSpec | Where-Object { $_.name -eq 'chromium' }).revision
    $localCache = Join-Path $env:LOCALAPPDATA "ms-playwright"
    $localChromium = Join-Path $localCache "chromium-$chromiumRevision"

    if (Test-Path -LiteralPath $localChromium) {
        Write-Step "Reusing installed Playwright browser"
        Get-ChildItem -LiteralPath $localCache -Directory |
            Where-Object { $_.Name -match '^(chromium|chromium_headless_shell|ffmpeg|winldd)-' } |
            ForEach-Object {
                Copy-CleanDirectory -Source $_.FullName -Destination (Join-Path $Destination $_.Name)
            }
    }
    else {
        Write-Step "Downloading bundled Chromium"
        $oldBrowsersPath = $env:PLAYWRIGHT_BROWSERS_PATH
        $env:PLAYWRIGHT_BROWSERS_PATH = $Destination
        try {
            & $PythonExe -m playwright install chromium
            if ($LASTEXITCODE -ne 0) {
                throw "Playwright Chromium installation failed"
            }
        }
        finally {
            $env:PLAYWRIGHT_BROWSERS_PATH = $oldBrowsersPath
        }
    }

    $oldBrowsersPath = $env:PLAYWRIGHT_BROWSERS_PATH
    $env:PLAYWRIGHT_BROWSERS_PATH = $Destination
    try {
        & $PythonExe -c "from pathlib import Path; from playwright.sync_api import sync_playwright; p=sync_playwright().start(); path=Path(p.chromium.executable_path); print(path); assert path.exists(); p.stop()"
        if ($LASTEXITCODE -ne 0) {
            throw "Bundled Chromium verification failed"
        }
    }
    finally {
        $env:PLAYWRIGHT_BROWSERS_PATH = $oldBrowsersPath
    }
}

function Build-GuiLauncher {
    param(
        [string]$RepoRoot,
        [string]$PackageDir,
        [string]$BuildRoot
    )

    $builderPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $builderPython)) {
        throw "Launcher build requires $builderPython"
    }

    & $builderPython -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Step "Installing launcher builder"
        & $builderPython -m pip install pyinstaller
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller installation failed"
        }
    }

    $launcherWork = Join-Path $BuildRoot "launcher-work"
    $launcherSpec = Join-Path $BuildRoot "launcher-spec"
    New-Item -ItemType Directory -Force -Path $launcherWork | Out-Null
    New-Item -ItemType Directory -Force -Path $launcherSpec | Out-Null

    Write-Step "Building Windows launcher"
    & $builderPython -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name "自媒体一键分发" `
        --distpath $PackageDir `
        --workpath $launcherWork `
        --specpath $launcherSpec `
        (Join-Path $RepoRoot "packaging\launcher.py")
    if ($LASTEXITCODE -ne 0) {
        throw "GUI launcher build failed"
    }
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$releaseRoot = Join-Path $repoRoot "release"
$buildRoot = Join-Path $repoRoot ".packaging-build"
$cacheDir = Join-Path $buildRoot "cache"
$packageDir = Join-Path $releaseRoot $PackageName
$programDir = Join-Path $packageDir "程序文件"

New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
Assert-ChildPath -Child $packageDir -Parent $releaseRoot

if (Test-Path -LiteralPath $packageDir) {
    Remove-Item -LiteralPath $packageDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $programDir | Out-Null

if (-not $SkipFrontendBuild) {
    Write-Step "Building frontend"
    Push-Location (Join-Path $repoRoot "frontend")
    try {
        if (Get-Command pnpm -ErrorAction SilentlyContinue) {
            & pnpm run build
        }
        elseif (Get-Command npm -ErrorAction SilentlyContinue) {
            & npm run build
        }
        else {
            throw "Neither pnpm nor npm is available"
        }
        if ($LASTEXITCODE -ne 0) {
            throw "frontend build failed"
        }
    }
    finally {
        Pop-Location
    }
}

$frontendDist = Join-Path $repoRoot "frontend\dist"
if (-not (Test-Path -LiteralPath $frontendDist)) {
    throw "frontend/dist does not exist"
}

Write-Step "Copying application into program folder"
foreach ($file in @("main.py", "conf.example.py", "requirements-oneclick.txt", "LICENSE", "NOTICE")) {
    $source = Join-Path $repoRoot $file
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $programDir $file) -Force
    }
}
Copy-Item -LiteralPath (Join-Path $repoRoot "conf.example.py") -Destination (Join-Path $programDir "conf.py") -Force

foreach ($dir in @("myUtils", "uploader", "utils")) {
    Copy-CleanDirectory -Source (Join-Path $repoRoot $dir) -Destination (Join-Path $programDir $dir)
}
Copy-CleanDirectory -Source $frontendDist -Destination (Join-Path $programDir "frontend\dist")

foreach ($runtimeDir in @("cookiesFile", "videoFile", "db", "logs", "avatars", ".starter")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $programDir $runtimeDir) | Out-Null
}

Build-GuiLauncher -RepoRoot $repoRoot -PackageDir $packageDir -BuildRoot $buildRoot

if (-not $SkipRuntimeInstall) {
    $runtimePythonDir = Join-Path $programDir "runtime\python"
    $pythonExe = Install-PortablePython -RuntimePythonDir $runtimePythonDir -CacheDir $cacheDir -Version $PythonVersion

    Write-Step "Installing Python dependencies"
    & $pythonExe -m pip install --no-warn-script-location -r (Join-Path $programDir "requirements-oneclick.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "dependency install failed"
    }

    $playwrightBrowsers = Join-Path $programDir "runtime\playwright-browsers"
    Install-BundledChromium -PythonExe $pythonExe -Destination $playwrightBrowsers
}

Write-Step "Checking package contents"
$blocked = @(
    "cookiesFile\*.json",
    "db\*.db",
    "logs\*.log",
    "avatars\*",
    "videoFile\*",
    ".git\*",
    ".venv\*",
    "frontend\node_modules\*"
)
foreach ($pattern in $blocked) {
    $matches = Get-ChildItem -LiteralPath $programDir -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName.Substring($programDir.Length + 1) -like $pattern }
    if ($matches) {
        throw "Package contains blocked runtime data matching $pattern"
    }
}

$rootItems = @(Get-ChildItem -LiteralPath $packageDir -Force)
$expectedNames = @("自媒体一键分发.exe", "程序文件")
$unexpected = @($rootItems | Where-Object { $_.Name -notin $expectedNames })
if ($rootItems.Count -ne 2 -or $unexpected.Count -gt 0) {
    throw "Package root must contain only the launcher and program folder"
}

Write-Host ""
Write-Host "Package folder: $packageDir" -ForegroundColor Green
Write-Host "Root contents: 自媒体一键分发.exe + 程序文件" -ForegroundColor Green
