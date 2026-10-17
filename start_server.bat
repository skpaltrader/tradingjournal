@echo off
title Quotex Trading Journal & P&L Server
cd /d "%~dp0"
echo ===================================================
echo   Quotex Trading Journal & P&L Analytics Server
echo   Default Credentials:
echo   Username: skpaltrader
echo   Password: success*
echo ===================================================
echo.
echo Starting server on http://localhost:8000 ...
echo Press Ctrl+C in this window to stop the server.
echo.

python -m pip install -r requirements.txt >nul 2>&1
start http://localhost:8000
python app.py
pause
