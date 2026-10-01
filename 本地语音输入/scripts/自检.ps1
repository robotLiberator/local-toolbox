$ErrorActionPreference = 'Stop'
$report = Join-Path $env:LOCALAPPDATA 'BubbleDictation\self-test.json'
$app = Join-Path $PSScriptRoot '本地语音输入.exe'
if (-not (Test-Path -LiteralPath $app)) { throw '请在发布文件夹中运行自检。' }
$process = Start-Process -FilePath $app -ArgumentList @('--self-test', '--report', ('"' + $report + '"')) -PassThru -Wait -WindowStyle Hidden
$result = Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
$result | Format-List
if ($process.ExitCode -ne 0 -or -not $result.passed) { throw "自检未通过，报告：$report" }
Write-Output '自检通过。此过程不访问麦克风、不输入文字、不修改剪贴板。'
