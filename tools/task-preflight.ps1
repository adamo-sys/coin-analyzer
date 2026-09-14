# Thin entry point: all argument parsing and repository logic live in Python.
# Select another existing interpreter with COIN_TASK_PYTHON when necessary.
$taskPython = if ($env:COIN_TASK_PYTHON) { $env:COIN_TASK_PYTHON } else { 'python' }
if (-not (Get-Command $taskPython -ErrorAction SilentlyContinue)) {
    [Console]::Error.WriteLine('Python is unavailable; select an installed interpreter with COIN_TASK_PYTHON.')
    exit 3
}
& $taskPython -B (Join-Path $PSScriptRoot 'task-state.py') preflight @args
exit $LASTEXITCODE
