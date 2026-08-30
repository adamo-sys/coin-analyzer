param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("LiveOutput", "IdleTree")]
    [string]$Mode,
    [string]$PidFile = ""
)

$ErrorActionPreference = "Stop"

if ($Mode -eq "LiveOutput") {
    Write-Output "DIAGNOSTIC_LIVE_OUTPUT_STARTED"
    [Console]::Error.WriteLine("DIAGNOSTIC_STDERR_VISIBLE")
    Start-Sleep -Seconds 5
    Write-Output "DIAGNOSTIC_LIVE_OUTPUT_FINISHED"
    exit 0
}

$child = Start-Process `
    -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -ArgumentList @("-NoProfile", "-Command", "Start-Sleep -Seconds 300") `
    -WindowStyle Hidden `
    -PassThru

if ($PidFile) {
    @($PID, $child.Id) | Set-Content -LiteralPath $PidFile -Encoding ASCII
}

Write-Output "DIAGNOSTIC_IDLE_TREE_STARTED parent_pid=$PID child_pid=$($child.Id)"
Start-Sleep -Seconds 300
