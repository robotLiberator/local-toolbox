param([string]$Original = 'E:\创世纪\auto-upload')
$ErrorActionPreference = 'Stop'
$productRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$originRoot = (Resolve-Path -LiteralPath $Original).Path
$sourceRoot = Join-Path $productRoot 'source'
$releaseRoot = Join-Path $productRoot 'dist\多平台分发'
if ((Test-Path -LiteralPath $sourceRoot) -or (Test-Path -LiteralPath $releaseRoot)) { throw '入库目标已存在，拒绝覆盖。' }

function Copy-ProductFiles([string]$Source, [string]$Destination) {
    $resolved = (Resolve-Path -LiteralPath $Source).Path
    $prefix = $resolved.TrimEnd('\') + '\'
    $blocked = @('__pycache__','node_modules','.git','.venv','.starter','cookiesFile','db','logs','avatars','videoFile','.pytest_cache','.links')
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-ChildItem -LiteralPath $resolved -Recurse -Force -File | ForEach-Object {
        $relative = $_.FullName.Substring($prefix.Length)
        foreach ($part in ($relative -split '[\\/]')) { if ($blocked -contains $part) { return } }
        if ($_.Name -match '(?i)(\.pyc$|\.log$|^account\.json$|cookie.*\.json$|token.*\.json$|\.env(?:\.|$))') { return }
        $target = Join-Path $Destination $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target
    }
}

New-Item -ItemType Directory -Path $sourceRoot -Force | Out-Null
foreach ($name in @('main.py','conf.example.py','requirements-oneclick.txt','LICENSE','NOTICE','README.md','SECURITY.md','bg1.png','start-oneclick.bat','run.bat','启动一键包.bat','新手使用说明.md','底座选型说明.md')) {
    $path = Join-Path $originRoot $name
    if (Test-Path -LiteralPath $path -PathType Leaf) { Copy-Item -LiteralPath $path -Destination (Join-Path $sourceRoot $name) }
}
Copy-Item -LiteralPath (Join-Path $sourceRoot 'conf.example.py') -Destination (Join-Path $sourceRoot 'conf.py')
foreach ($name in @('myUtils','uploader','utils','tests','packaging','scripts','licenses','frontend\src','frontend\public')) {
    $path = Join-Path $originRoot $name
    if (Test-Path -LiteralPath $path -PathType Container) { Copy-ProductFiles $path (Join-Path $sourceRoot $name) }
}
foreach ($name in @('frontend\package.json','frontend\package-lock.json','frontend\pnpm-lock.yaml','frontend\pnpm-workspace.yaml','frontend\index.html','frontend\vite.config.js','frontend\README.md','docs\一键分发整合包.md')) {
    $path = Join-Path $originRoot $name
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $target = Join-Path $sourceRoot $name
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $path -Destination $target
    }
}

$existing = Join-Path $originRoot 'release\自媒体一键分发'
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $existing '自媒体一键分发.exe') -Destination $releaseRoot
$program = Join-Path $releaseRoot '程序文件'
New-Item -ItemType Directory -Path $program -Force | Out-Null
foreach ($name in @('main.py','conf.example.py','requirements-oneclick.txt','LICENSE','NOTICE')) {
    Copy-Item -LiteralPath (Join-Path $sourceRoot $name) -Destination $program
}
Copy-Item -LiteralPath (Join-Path $sourceRoot 'conf.example.py') -Destination (Join-Path $program 'conf.py')
foreach ($name in @('myUtils','uploader','utils')) { Copy-ProductFiles (Join-Path $sourceRoot $name) (Join-Path $program $name) }
Copy-ProductFiles (Join-Path $originRoot 'frontend\dist') (Join-Path $program 'frontend\dist')
Copy-ProductFiles (Join-Path $existing '程序文件\runtime') (Join-Path $program 'runtime')
foreach ($name in @('cookiesFile','videoFile','db','logs','avatars','.starter')) { New-Item -ItemType Directory -Path (Join-Path $program $name) -Force | Out-Null }
Copy-Item -LiteralPath (Join-Path $originRoot 'packaging\README-zh-CN.txt') -Destination $releaseRoot
Copy-Item -LiteralPath (Join-Path $sourceRoot 'LICENSE'),(Join-Path $sourceRoot 'NOTICE') -Destination $releaseRoot
Write-Output ('源码入库：' + $sourceRoot)
Write-Output ('一键产品：' + $releaseRoot)
