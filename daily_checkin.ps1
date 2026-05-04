$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $repo "daily_checkin.log"

Set-Location -LiteralPath $repo

$startedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$startedAt] Starting daily check-in" | Add-Content -LiteralPath $log -Encoding UTF8

py -3 .\autofill_login.py --check-in --no-start-wait --no-close-wait *>&1 |
    Tee-Object -FilePath $log -Append

exit $LASTEXITCODE
