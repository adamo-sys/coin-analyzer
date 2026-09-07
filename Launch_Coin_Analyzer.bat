@echo off
setlocal
set "APP_DIR=%~dp0"
set "APP_FILE=%APP_DIR%coin_analyzer_startup.py"
if not exist "%APP_FILE%" (
    echo Coin Analyzer startup files are missing. Keep the launcher in the project folder.
    pause
    exit /b 1
)
if exist "%APP_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%APP_DIR%.venv\Scripts\python.exe"
    goto run
)
python --version >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_EXE=python"
    goto run
)
py --version >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_EXE=py"
    goto run
)
echo Python was not found. Install Python 3.12+ and create the project .venv.
pause
exit /b 1
:run
pushd "%APP_DIR%" >nul
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" "%APP_FILE%"
set "APP_EXIT=%ERRORLEVEL%"
popd >nul
if not "%APP_EXIT%"=="0" pause
exit /b %APP_EXIT%
