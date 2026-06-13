@echo off
chcp 65001 >nul
title Stock Analyzer
echo Starting server...
start "Stock Analyzer" /B python "C:\Users\10177\Desktop\reasonix-project\Project_01_股票分析工具优化\launcher.py"
timeout /t 3 /nobreak >nul
start http://127.0.0.1:8765
echo.
echo Browser: http://127.0.0.1:8765
echo Close this window to stop.
pause
