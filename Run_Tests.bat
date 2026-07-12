@echo off
setlocal

set "APP_DIR=%~dp0"
pushd "%APP_DIR%" >nul

python --version >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_EXE=python"
) else (
    py --version >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON_EXE=py"
    )
)

if not defined PYTHON_EXE (
    echo Python could not be found.
    echo Install Python, then run this file again.
    popd >nul
    pause
    exit /b 1
)

"%PYTHON_EXE%" -m unittest discover
set "TEST_EXIT=%ERRORLEVEL%"

echo.
if "%TEST_EXIT%"=="0" (
    echo Tests completed successfully.
) else (
    echo Tests failed with exit code %TEST_EXIT%.
)

popd >nul
pause
exit /b %TEST_EXIT%
