@echo off
setlocal

set "APP_DIR=%~dp0"

if not exist "%APP_DIR%coin_collection_gui.py" (
    echo Coin Analyzer could not be found.
    echo Expected:
    echo   "%APP_DIR%coin_collection_gui.py"
    echo.
    echo Keep this launcher in the Coin Analyzer project folder.
    pause
    exit /b 1
)

start "Coin Analyzer Developer Mode" %ComSpec% /k cd /d "%APP_DIR%"

endlocal
exit /b 0
