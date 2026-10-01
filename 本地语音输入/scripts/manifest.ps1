param([string]$Release = (Join-Path $PSScriptRoot '..\dist\本地语音输入'))
$ErrorActionPreference = 'Stop'
$releaseRoot = (Resolve-Path -LiteralPath $Release).Path
$entries = @(Get-ChildItem -LiteralPath $releaseRoot -Recurse -File | Where-Object {$_.Name -ne 'manifest.json'} | Sort-Object FullName | ForEach-Object {
    [PSCustomObject]@{
        path = $_.FullName.Substring($releaseRoot.Length + 1).Replace('\','/')
        bytes = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
})
$manifest = [PSCustomObject]@{ version='1.0.1'; file_count=$entries.Count; total_bytes=($entries | Measure-Object bytes -Sum).Sum; files=$entries }
[IO.File]::WriteAllText((Join-Path $releaseRoot 'manifest.json'), ($manifest | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
Write-Output "校验清单生成：$($entries.Count) 个文件"
