@echo off
setlocal

set "APP_DIR=%~dp0"
set "APP_FILE=%APP_DIR%coin_collection_gui.py"

if not exist "%APP_FILE%" (
    echo Coin Analyzer could not be found.
    echo Expected:
    echo   "%APP_FILE%"
    echo.
    echo Keep this launcher in the Coin Analyzer project folder.
    pause
    exit /b 1
)

pythonw --version >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_EXE=pythonw"
) else (
    python --version >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON_EXE=python"
    ) else (
        py --version >nul 2>nul
        if %errorlevel%==0 (
            set "PYTHON_EXE=py"
        )
    )
)

if not defined PYTHON_EXE (
    echo Python could not be found.
    echo Install Python, then try this launcher again.
    echo.
    echo If Python is installed, you can also try from a terminal:
    echo   py coin_collection_gui.py
    pause
    exit /b 1
)

pushd "%APP_DIR%" >nul
start "" "%PYTHON_EXE%" "%APP_FILE%"
if errorlevel 1 (
    popd >nul
    echo Coin Analyzer could not be started with %PYTHON_EXE%.
    echo Try from a terminal:
    echo   python coin_collection_gui.py
    echo or:
    echo   py coin_collection_gui.py
    pause
    exit /b 1
)
popd >nul

endlocal
exit /b 0
