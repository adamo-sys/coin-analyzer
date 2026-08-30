param(
    [Parameter(Mandatory = $true)]
    [string]$PromptFile,
    [string]$ExpectedHead = "",
    [ValidateRange(1, 10080)]
    [int]$IdleTimeoutMinutes = 30,
    [ValidateRange(0, 86400)]
    [int]$IdleTimeoutSeconds = 0,
    [ValidateRange(1, 43200)]
    [int]$MaxRuntimeMinutes = 480,
    [ValidateRange(0, 86400)]
    [int]$MaxRuntimeSeconds = 0,
    [ValidateSet("None", "LiveOutput", "IdleTree")]
    [string]$DiagnosticMode = "None",
    [string]$DiagnosticPidFile = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class CoinAnalyzerProcessTreeSnapshot
{
    private const uint TH32CS_SNAPPROCESS = 0x00000002;
    private static readonly IntPtr InvalidHandleValue = new IntPtr(-1);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    private struct PROCESSENTRY32
    {
        public uint dwSize;
        public uint cntUsage;
        public uint th32ProcessID;
        public IntPtr th32DefaultHeapID;
        public uint th32ModuleID;
        public uint cntThreads;
        public uint th32ParentProcessID;
        public int pcPriClassBase;
        public uint dwFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
        public string szExeFile;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint processId);

    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern bool Process32First(IntPtr snapshot, ref PROCESSENTRY32 entry);

    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern bool Process32Next(IntPtr snapshot, ref PROCESSENTRY32 entry);

    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);

    public static int[] GetDescendantIds(int rootProcessId)
    {
        var parentById = new Dictionary<int, int>();
        IntPtr snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if (snapshot == InvalidHandleValue)
            throw new Win32Exception(Marshal.GetLastWin32Error());

        try
        {
            var entry = new PROCESSENTRY32();
            entry.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));
            if (Process32First(snapshot, ref entry))
            {
                do
                {
                    parentById[(int)entry.th32ProcessID] = (int)entry.th32ParentProcessID;
                    entry.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));
                }
                while (Process32Next(snapshot, ref entry));
            }
        }
        finally
        {
            CloseHandle(snapshot);
        }

        var descendants = new List<int>();
        var frontier = new Queue<int>();
        frontier.Enqueue(rootProcessId);
        while (frontier.Count > 0)
        {
            int parentId = frontier.Dequeue();
            foreach (var pair in parentById)
            {
                if (pair.Value == parentId)
                {
                    descendants.Add(pair.Key);
                    frontier.Enqueue(pair.Key);
                }
            }
        }
        return descendants.ToArray();
    }
}
"@

function Write-JobLogLine {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.StreamWriter]$Writer,
        [AllowEmptyString()]
        [string]$Text = ""
    )

    $Writer.WriteLine($Text)
    $Writer.Flush()
}

function Stop-LaunchedProcessTree {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)]
        [System.IO.StreamWriter]$Writer,
        [Parameter(Mandatory = $true)]
        [string]$Reason
    )

    if ($Process.HasExited) {
        return
    }

    $targetPid = $Process.Id
    $descendantIds = @([CoinAnalyzerProcessTreeSnapshot]::GetDescendantIds($targetPid))
    Write-JobLogLine $Writer "PROCESS_TREE_TERMINATION reason=$Reason root_pid=$targetPid"
    Write-JobLogLine $Writer "PROCESS_TREE_DESCENDANTS $($descendantIds -join ',')"
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # taskkill can report a nonzero result when one member exits during the
        # traversal. Capture that diagnostic without allowing it to bypass the
        # bounded wait and exact-PID fallback below.
        $ErrorActionPreference = "Continue"
        $taskkillOutput = @(& "$env:SystemRoot\System32\taskkill.exe" /PID $targetPid /T /F 2>&1)
        $taskkillExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    foreach ($line in $taskkillOutput) {
        Write-JobLogLine $Writer "[TASKKILL] $line"
    }

    Write-JobLogLine $Writer "TASKKILL_EXIT_CODE $taskkillExitCode"

    if ($taskkillExitCode -ne 0 -or -not $Process.WaitForExit(10000)) {
        Write-JobLogLine $Writer "PROCESS_TREE_TERMINATION_FALLBACK root_pid=$targetPid"
        Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
        [Array]::Reverse($descendantIds)
        foreach ($descendantId in $descendantIds) {
            Stop-Process -Id $descendantId -Force -ErrorAction SilentlyContinue
        }
        if (-not $Process.WaitForExit(5000)) {
            throw "Could not terminate launched process tree rooted at PID $targetPid"
        }
    }
}

function Write-FinalGitState {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.StreamWriter]$Writer
    )

    Write-JobLogLine $Writer ""
    Write-JobLogLine $Writer "===== FINAL GIT STATE ====="

    try {
        $finalHead = (& git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "git rev-parse failed with exit code $LASTEXITCODE"
        }

        Write-JobLogLine $Writer "HEAD $finalHead"
        $finalStatus = @(& git status --short)
        if ($LASTEXITCODE -ne 0) {
            throw "git status failed with exit code $LASTEXITCODE"
        }

        if ($finalStatus.Count -eq 0) {
            Write-JobLogLine $Writer "STATUS (clean)"
        }
        else {
            foreach ($line in $finalStatus) {
                Write-JobLogLine $Writer $line
            }
        }
    }
    catch {
        Write-JobLogLine $Writer "FINAL_GIT_STATE_ERROR $($_.Exception.Message)"
    }
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repo
$codex = Join-Path $env:APPDATA "npm\codex.cmd"
$logsDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force $logsDir | Out-Null

if ([System.IO.Path]::IsPathRooted($PromptFile)) {
    $promptPath = $PromptFile
}
else {
    $promptPath = Join-Path $repo $PromptFile
}

if (-not (Test-Path -LiteralPath $promptPath -PathType Leaf)) {
    throw "Prompt file does not exist: $promptPath"
}
if (-not (Test-Path -LiteralPath $codex -PathType Leaf)) {
    throw "Codex executable does not exist: $codex"
}

$prompt = Get-Content -LiteralPath $promptPath -Raw
$promptLength = $prompt.Length
$firstLine = (($prompt -split "`r?`n")[0]).Trim()
if ($promptLength -lt 500) {
    throw "Prompt is suspiciously short: $promptLength characters"
}
if ([string]::IsNullOrWhiteSpace($firstLine)) {
    throw "Prompt first line is empty"
}

$head = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Could not resolve Git HEAD"
}
if ($ExpectedHead -and -not $head.StartsWith($ExpectedHead, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "HEAD mismatch. Expected $ExpectedHead, found $head"
}

$trackedDirty = @(& git status --porcelain --untracked-files=no)
if ($LASTEXITCODE -ne 0) {
    throw "git status failed"
}
if ($trackedDirty.Count -gt 0) {
    throw "Tracked working tree is dirty:`n$($trackedDirty -join "`n")"
}

Write-Host "PROMPT_EXISTS True"
Write-Host "PROMPT_LENGTH $promptLength"
Write-Host "FIRST_LINE $firstLine"
Write-Host "CODEX_EXISTS True"
Write-Host "CODEX_PATH $codex"
Write-Host "HEAD $head"
Write-Host "TRACKED_DIRTY False"

if ($DryRun) {
    Write-Host "DRY_RUN PASS"
    exit 0
}

$idleTimeout = if ($IdleTimeoutSeconds -gt 0) {
    [TimeSpan]::FromSeconds($IdleTimeoutSeconds)
}
else {
    [TimeSpan]::FromMinutes($IdleTimeoutMinutes)
}
$maxRuntime = if ($MaxRuntimeSeconds -gt 0) {
    [TimeSpan]::FromSeconds($MaxRuntimeSeconds)
}
else {
    [TimeSpan]::FromMinutes($MaxRuntimeMinutes)
}

$mutex = New-Object System.Threading.Mutex($false, "Local\CoinAnalyzerCodexJob")
$hasLock = $false
$writer = $null
$process = $null
$exitCode = 1
$timedOut = $false
$logPath = ""

try {
    $hasLock = $mutex.WaitOne(0)
    if (-not $hasLock) {
        throw "Another Coin Analyzer Codex job is already running"
    }

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $jobName = [System.IO.Path]::GetFileNameWithoutExtension($promptPath)
    $logPath = Join-Path $logsDir "$timestamp-$jobName.log"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $writer = New-Object System.IO.StreamWriter($logPath, $false, $utf8NoBom)
    $writer.AutoFlush = $true

    foreach ($line in @(
        "===== CODEX JOB START =====",
        "START $(Get-Date -Format o)",
        "PROMPT $promptPath",
        "PROMPT_LENGTH $promptLength",
        "FIRST_LINE $firstLine",
        "CODEX $codex",
        "HEAD $head",
        "TRACKED_DIRTY False",
        "IDLE_TIMEOUT $($idleTimeout.ToString())",
        "MAX_RUNTIME $($maxRuntime.ToString())",
        "DIAGNOSTIC_MODE $DiagnosticMode",
        "LAUNCHING",
        ""
    )) {
        Write-JobLogLine $writer $line
    }

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.WorkingDirectory = $repo
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    if ($DiagnosticMode -eq "None") {
        $psi.FileName = $codex
        $psi.Arguments = "exec --approve-for-me -"
    }
    else {
        $diagnosticChild = Join-Path $PSScriptRoot "test_codex_job_child.ps1"
        if (-not (Test-Path -LiteralPath $diagnosticChild -PathType Leaf)) {
            throw "Diagnostic child not found: $diagnosticChild"
        }

        $psi.FileName = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
        $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$diagnosticChild`" -Mode $DiagnosticMode -PidFile `"$DiagnosticPidFile`""
    }

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    if (-not $process.Start()) {
        throw "Failed to start Codex"
    }

    Write-JobLogLine $writer "CODEX STARTED PID $($process.Id)"
    $stdoutTask = $process.StandardOutput.ReadLineAsync()
    $stderrTask = $process.StandardError.ReadLineAsync()
    $stdoutClosed = $false
    $stderrClosed = $false
    $startedUtc = [DateTime]::UtcNow
    $lastProgressUtc = $startedUtc
    $postExitDeadlineUtc = [DateTime]::MaxValue

    if ($DiagnosticMode -eq "None") {
        $process.StandardInput.Write($prompt)
    }
    $process.StandardInput.Close()

    while (-not ($process.HasExited -and $stdoutClosed -and $stderrClosed)) {
        while (-not $stdoutClosed -and $stdoutTask.IsCompleted) {
            $line = $stdoutTask.GetAwaiter().GetResult()
            if ($null -eq $line) {
                $stdoutClosed = $true
            }
            else {
                Write-JobLogLine $writer "[STDOUT] $line"
                $lastProgressUtc = [DateTime]::UtcNow
                $stdoutTask = $process.StandardOutput.ReadLineAsync()
            }
        }

        while (-not $stderrClosed -and $stderrTask.IsCompleted) {
            $line = $stderrTask.GetAwaiter().GetResult()
            if ($null -eq $line) {
                $stderrClosed = $true
            }
            else {
                Write-JobLogLine $writer "[STDERR] $line"
                $lastProgressUtc = [DateTime]::UtcNow
                $stderrTask = $process.StandardError.ReadLineAsync()
            }
        }

        if (-not $process.HasExited) {
            $watchdogUtc = [DateTime]::UtcNow
            $idleFor = $watchdogUtc - $lastProgressUtc
            $runFor = $watchdogUtc - $startedUtc
            if ($runFor -ge $maxRuntime) {
                $timedOut = $true
                Write-JobLogLine $writer "WATCHDOG_MAX_RUNTIME runtime_seconds=$([Math]::Round($runFor.TotalSeconds, 1)) limit_seconds=$([Math]::Round($maxRuntime.TotalSeconds, 1)) root_pid=$($process.Id)"
                Stop-LaunchedProcessTree -Process $process -Writer $writer -Reason "maximum-runtime"
            }
            elseif ($idleFor -ge $idleTimeout) {
                $timedOut = $true
                Write-JobLogLine $writer "WATCHDOG_TIMEOUT idle_seconds=$([Math]::Round($idleFor.TotalSeconds, 1)) limit_seconds=$([Math]::Round($idleTimeout.TotalSeconds, 1)) root_pid=$($process.Id)"
                Stop-LaunchedProcessTree -Process $process -Writer $writer -Reason "idle-watchdog"
            }
            else {
                [void]$process.WaitForExit(100)
            }
        }
        else {
            if ($postExitDeadlineUtc -eq [DateTime]::MaxValue) {
                $postExitDeadlineUtc = [DateTime]::UtcNow.AddSeconds(10)
            }
            if ([DateTime]::UtcNow -ge $postExitDeadlineUtc -and (-not $stdoutClosed -or -not $stderrClosed)) {
                Write-JobLogLine $writer "OUTPUT_DRAIN_TIMEOUT Streams did not close within 10 seconds of child exit"
                $process.StandardOutput.Close()
                $process.StandardError.Close()
                $exitCode = 125
                break
            }
            Start-Sleep -Milliseconds 50
        }
    }

    if ($process.HasExited -and $exitCode -ne 125) {
        $process.WaitForExit()
        $exitCode = if ($timedOut) { 124 } else { $process.ExitCode }
    }

    Write-JobLogLine $writer ""
    Write-JobLogLine $writer "EXIT_CODE $exitCode"
}
catch {
    $exitCode = 1
    if ($null -ne $writer) {
        Write-JobLogLine $writer "RUNNER_ERROR $($_.Exception.Message)"
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-LaunchedProcessTree -Process $process -Writer $writer -Reason "runner-error"
        }
        Write-JobLogLine $writer "EXIT_CODE $exitCode"
    }
    else {
        Write-Error $_
    }
}
finally {
    if ($null -ne $writer) {
        Write-FinalGitState $writer
        Write-JobLogLine $writer "FINISHED $(Get-Date -Format o)"
        Write-JobLogLine $writer "===== CODEX JOB END ====="
        $writer.Dispose()
    }
    if ($null -ne $process) {
        $process.Dispose()
    }
    if ($hasLock) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}

Write-Host "CODEX_EXIT_CODE $exitCode"
Write-Host "LOG $logPath"
exit $exitCode
