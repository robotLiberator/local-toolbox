param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference = 'Stop'
$productRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$toolboxRoot = (Resolve-Path (Join-Path $productRoot '..')).Path
$release = Join-Path $productRoot 'dist\本地语音输入'
$version = (Get-Content -LiteralPath (Join-Path $release 'manifest.json') -Raw | ConvertFrom-Json).version
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$backupRoot = (Resolve-Path -LiteralPath $Destination).Path
$releaseZip = Join-Path $backupRoot "本地语音输入-Windows-x64-v$version.zip"
$sourceZip = Join-Path $backupRoot "工具箱-源码-v$version.zip"
if ((Test-Path -LiteralPath $releaseZip) -or (Test-Path -LiteralPath $sourceZip)) { throw '目标已有备份，请选择新的备份文件夹，避免覆盖。' }
Compress-Archive -LiteralPath $release -DestinationPath $releaseZip -CompressionLevel Fastest
& git -C $toolboxRoot archive --format=zip ('--output=' + $sourceZip) HEAD
if ($LASTEXITCODE -ne 0) { throw '源码归档失败' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($releaseZip)
try {
    $expected = (Get-ChildItem -LiteralPath $release -Recurse -File).Count
    $actual = @($archive.Entries | Where-Object { -not $_.FullName.EndsWith('/') }).Count
    if ($actual -ne $expected) { throw "备份文件数不符：$actual / $expected" }
} finally { $archive.Dispose() }
$entries = @($releaseZip,$sourceZip) | ForEach-Object {
    $file = Get-Item -LiteralPath $_
    [PSCustomObject]@{name=$file.Name;bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$info = [PSCustomObject]@{version=$version;created_utc=(Get-Date).ToUniversalTime().ToString('o');git_commit=(& git -C $toolboxRoot rev-parse HEAD);archives=$entries}
[IO.File]::WriteAllText((Join-Path $backupRoot '校验清单.json'),($info | ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
Write-Output ($info | ConvertTo-Json -Depth 5)
