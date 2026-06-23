@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Auto Script Studio
cd /d "%~dp0"

echo ========================================
echo   Auto Script Studio 一键启动
echo   PC 开发助手：工程 / 抓抓 / Lua 脚本
echo   关闭本窗口即退出 Studio
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 Python，请先安装 Python 3.10+ 并加入 PATH
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [首次运行] 正在创建虚拟环境...
  python -m venv .venv
  if errorlevel 1 (
    echo [错误] 创建虚拟环境失败
    pause
    exit /b 1
  )
)

echo [安装] 检查 Studio 依赖（首次约需 5-15 分钟，PySide6 较大）...
".venv\Scripts\python.exe" -m pip install -q --upgrade pip
".venv\Scripts\pip.exe" install --default-timeout=120 -i https://pypi.tuna.tsinghua.edu.cn/simple -r studio\requirements.txt
if errorlevel 1 (
  echo [重试] 换官方源再试一次...
  ".venv\Scripts\pip.exe" install --default-timeout=300 -r studio\requirements.txt
)
if errorlevel 1 (
  echo [错误] 依赖安装失败，请检查网络后重试 start.cmd
  pause
  exit /b 1
)

if exist "..\adb-ide\requirements.txt" (
  echo [安装] 检测到同级 adb-ide，安装完整 IDE 依赖...
  ".venv\Scripts\pip.exe" install --default-timeout=120 -i https://pypi.tuna.tsinghua.edu.cn/simple -r ..\adb-ide\requirements.txt
) else (
  echo [提示] 未找到 ..\adb-ide，将使用简易 Studio 界面
  echo         完整 IDE 请将 adb-ide 放在: %~dp0..\adb-ide
)
echo.

call ".venv\Scripts\activate.bat"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo [启动] Auto Script Studio...
echo.
python -m studio.main
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo [错误] Studio 异常退出，代码: %EXIT_CODE%
  pause
)

endlocal & exit /b %EXIT_CODE%
