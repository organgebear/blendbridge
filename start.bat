@echo off
chcp 65001 >nul 2>&1

:: ═══════════════════════════════════════════════════════════════════
:: BlendBridge — 启动脚本 (Windows)
::
:: 零依赖：仅需系统自带 Python 3 + Blender
:: 无需 pip install、无需下载任何东西
::
:: 用法: 双击 start.bat 或在命令行运行
:: ═══════════════════════════════════════════════════════════════════

cd /d "%~dp0"

echo.
echo ╔══════════════════════════════════════════════╗
echo ║      🌉  BlendBridge                         ║
echo ║      Blender FBX 纹理修复工具                ║
echo ╚══════════════════════════════════════════════╝
echo.

:: ── 查找 Python ──────────────────────────────────────────────────
set "PYTHON="
for %%p in (python3 python py) do (
    where %%p >nul 2>&1
    if !errorlevel!==0 (
        for /f "tokens=*" %%v in ('%%p -c "import sys; print(sys.version_info.major)" 2^>nul') do (
            if %%v GEQ 3 (
                set "PYTHON=%%p"
                goto :found_python
            )
        )
    )
)

echo ❌ 未找到 Python 3
echo.
echo    Microsoft Store: 搜索 "Python 3.12"
echo    官网: https://www.python.org/downloads/
echo.
pause
exit /b 1

:found_python
echo   🐍 已找到 Python 3

:: ── 检查 Blender ─────────────────────────────────────────────────
set "BLENDER="
if exist "C:\Program Files\Blender Foundation\Blender\blender.exe" (
    set "BLENDER=C:\Program Files\Blender Foundation\Blender\blender.exe"
) else (
    where blender >nul 2>&1
    if !errorlevel!==0 set "BLENDER=blender"
)

if defined BLENDER (
    echo   🎨 已找到 Blender
) else (
    echo   ⚠️  未找到 Blender（不影响启动，但无法处理文件）
)
echo.

:: ── 启动 ─────────────────────────────────────────────────────────
echo   启动中 → http://localhost:5000
echo.

:: 打开浏览器
start "" "http://localhost:5000"

cd /d "%~dp0backend"
"%PYTHON%" server.py

echo.
echo 已停止
pause
