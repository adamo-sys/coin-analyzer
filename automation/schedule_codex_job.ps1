param(
    [Parameter(Mandatory = $true)]
    [string]$TaskName,

    [Parameter(Mandatory = $true)]
    [string]$PromptFile,

    [Parameter(Mandatory = $true)]
    [datetime]$RunAt,

    [string]$ExpectedHead = "",

    [ValidateRange(1, 10080)]
    [int]$IdleTimeoutMinutes = 30,

    [ValidateRange(1, 43200)]
    [int]$MaxRuntimeMinutes = 480
)

$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runner = Join-Path $repo "automation\run_codex_job.ps1"

if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw "Runner not found: $runner"
}

$promptPath = $null
if ([System.IO.Path]::IsPathRooted($PromptFile)) {
    $promptPath = $PromptFile
}
else {
    $promptPath = Join-Path $repo $PromptFile
}

if (-not (Test-Path -LiteralPath $promptPath -PathType Leaf)) {
    throw "Prompt not found: $promptPath"
}

$arguments = @(
    "-NoProfile"
    "-ExecutionPolicy", "Bypass"
    "-File", "`"$runner`""
    "-PromptFile", "`"$promptPath`""
)

if ($ExpectedHead) {
    $arguments += @("-ExpectedHead", "`"$ExpectedHead`"")
}

$arguments += @("-IdleTimeoutMinutes", $IdleTimeoutMinutes)
$arguments += @("-MaxRuntimeMinutes", $MaxRuntimeMinutes)

$argumentString = $arguments -join " "

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $argumentString `
    -WorkingDirectory $repo

$trigger = New-ScheduledTaskTrigger -Once -At $RunAt

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Force | Out-Null

$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName

Write-Host "TASK_NAME $TaskName"
Write-Host "STATE $($task.State)"
Write-Host "NEXT_RUN $($info.NextRunTime)"
Write-Host "PROMPT $promptPath"
Write-Host "EXPECTED_HEAD $ExpectedHead"
Write-Host "IDLE_TIMEOUT_MINUTES $IdleTimeoutMinutes"
Write-Host "MAX_RUNTIME_MINUTES $MaxRuntimeMinutes"
Write-Host "RUNNER $runner"
