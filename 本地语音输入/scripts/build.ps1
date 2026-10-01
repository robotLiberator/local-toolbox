param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$productRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $productRoot
try {
    & $Python 'scripts\make_icon.py'
    if ($LASTEXITCODE -ne 0) { throw '图标生成失败' }
    & $Python -m PyInstaller --noconfirm --clean --workpath '.build' --distpath 'dist' 'product.spec'
    if ($LASTEXITCODE -ne 0) { throw '应用构建失败' }
    $release = Join-Path $productRoot 'dist\本地语音输入'
    Copy-Item -LiteralPath (Join-Path $productRoot 'models') -Destination $release -Recurse -Force
    $engine = Join-Path $release 'runtime\llama'
    New-Item -ItemType Directory -Path $engine -Force | Out-Null
    $runtime = Join-Path $productRoot 'runtime\llama'
    $files = Get-ChildItem -LiteralPath $runtime -File | Where-Object {
        $_.Name -eq 'llama-server.exe' -or $_.Name -match '^(ggml.*\.dll|llama(?:-common|-server-impl)?\.dll|mtmd\.dll|libomp\.dll|LICENSE.*)$'
    }
    foreach ($file in $files) { Copy-Item -LiteralPath $file.FullName -Destination $engine -Force }
    foreach ($name in @('cleanup_prompt.txt','cleanup_sources.json','README.md','THIRD_PARTY_NOTICES.md','LICENSE')) {
        Copy-Item -LiteralPath (Join-Path $productRoot $name) -Destination $release -Force
    }
    Copy-Item -LiteralPath (Join-Path $productRoot 'scripts\自检.ps1') -Destination $release -Force
    foreach ($folder in @('licenses','docs')) {
        Copy-Item -LiteralPath (Join-Path $productRoot $folder) -Destination $release -Recurse -Force
    }
    & (Join-Path $PSScriptRoot 'manifest.ps1') -Release $release
    Write-Output "构建完成：$release"
} finally { Pop-Location }
