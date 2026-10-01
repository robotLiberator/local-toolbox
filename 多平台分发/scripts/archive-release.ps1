param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference = 'Stop'
$productRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$release = (Resolve-Path -LiteralPath (Join-Path $productRoot 'dist\多平台分发')).Path
$source = (Resolve-Path -LiteralPath (Join-Path $productRoot 'source')).Path
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$destinationRoot = (Resolve-Path -LiteralPath $Destination).Path
$releaseZip = Join-Path $destinationRoot 'multi-platform-publisher-windows-x64-2026.10.01.zip'
$sourceZip = Join-Path $destinationRoot 'multi-platform-publisher-source-2026.10.01.zip'
if ((Test-Path -LiteralPath $releaseZip) -or (Test-Path -LiteralPath $sourceZip)) { throw '目标已有归档，拒绝覆盖。' }
foreach ($name in @('cookiesFile','videoFile','db','logs','avatars','.starter')) {
    if (Get-ChildItem -LiteralPath (Join-Path $release ('程序文件\'+$name)) -Force -Recurse -File) { throw ('运行数据不为空：'+$name) }
}
$files = @(Get-ChildItem -LiteralPath $release -Recurse -File | Sort-Object FullName | ForEach-Object {
    [PSCustomObject]@{path=$_.FullName.Substring($release.Length+1).Replace('\','/');bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
})
$manifest = [PSCustomObject]@{version='2026.10.01';file_count=$files.Count;total_bytes=($files|Measure-Object bytes -Sum).Sum;files=$files}
[IO.File]::WriteAllText((Join-Path $release 'manifest.json'),($manifest|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
Compress-Archive -LiteralPath $release -DestinationPath $releaseZip -CompressionLevel Optimal
$toolboxRoot = (Resolve-Path -LiteralPath (Join-Path $productRoot '..')).Path
& git -C $toolboxRoot archive --format=zip ('--output='+$sourceZip) HEAD -- '多平台分发' '产品封装标准.md' 'AGENTS.md'
if ($LASTEXITCODE -ne 0) { throw '源码归档失败，请先提交入库文件。' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($releaseZip)
try {
    $actual = @($archive.Entries | Where-Object {-not $_.FullName.EndsWith('/')}).Count
    if ($actual -ne $files.Count+1) { throw '发布归档文件数不符。' }
} finally { $archive.Dispose() }
$archives = @($releaseZip,$sourceZip) | ForEach-Object {
    $item = Get-Item -LiteralPath $_
    [PSCustomObject]@{name=$item.Name;bytes=$item.Length;sha256=(Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$record = [PSCustomObject]@{version='2026.10.01';created_utc=(Get-Date).ToUniversalTime().ToString('o');archives=$archives}
[IO.File]::WriteAllText((Join-Path $destinationRoot '校验清单.json'),($record | ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
Write-Output ($record | ConvertTo-Json -Depth 5)
