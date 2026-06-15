@echo off
setlocal

where py >nul 2>nul
if %errorlevel%==0 (
    py -m unittest discover -s . -p "test_*.py"
) else (
    python -m unittest discover -s . -p "test_*.py"
)

exit /b %errorlevel%
