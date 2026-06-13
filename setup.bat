@echo off
REM Stock Analyzer — 一键环境设置脚本
echo.
echo ========================================
echo   Stock Analyzer — 环境设置
echo ========================================
echo.

REM 创建虚拟环境
if not exist ".venv" (
    echo [1/3] 创建虚拟环境...
    python -m venv .venv
) else (
    echo [1/3] 虚拟环境已存在
)

REM 激活并安装依赖
echo [2/3] 安装依赖...
call .venv\Scripts\pip install -r requirements.txt

echo [3/3] 验证安装...
call .venv\Scripts\python -c "import stock_analyzer; print('OK: stock_analyzer v' + stock_analyzer.__version__)"

echo.
echo ✅ 环境设置完成!
echo.
echo 使用方法:
echo   .venv\Scripts\python -m stock_analyzer.main basic
echo   .venv\Scripts\stock basic
echo.
pause
