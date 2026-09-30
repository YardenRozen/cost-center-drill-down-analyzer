@echo off
REM Launches the Cost-Center Drill-Down Analyzer and opens it in the browser.
REM Double-click to run. Close this window to stop the server.

chcp 65001 >nul
title Cost-Center Drill-Down Analyzer

REM Run from the folder this file lives in (works via a desktop shortcut too)
cd /d "%~dp0"

echo Starting the dashboard... the browser will open automatically.
echo Close this window to stop the server.
echo.

python -m streamlit run app.py --server.headless false

REM Keep the window open if the server exits with an error
if errorlevel 1 pause
