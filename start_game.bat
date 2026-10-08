@echo off
chcp 65001 >nul
cd /d "%~dp0"
where conda >nul 2>nul
if errorlevel 1 (
    python start.py %*
) else (
    call conda run -n cardgame --no-capture-output python start.py %*
)
set "game_exit_code=%errorlevel%"
if not "%game_exit_code%"=="0" echo 启动失败。请检查 cardgame 环境、requirements.txt 依赖及 logs\startup_error.log。
pause
exit /b %game_exit_code%
