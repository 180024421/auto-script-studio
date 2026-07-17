@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Auto Script Studio
cd /d "%~dp0"

echo ========================================
echo   Auto Script Studio 一键启动
echo   PC 开发助手：工程 / 抓抓 / 浮动面板 / Lua 脚本
echo   关闭本窗口即退出 Studio
echo ========================================
echo.

set "PY="
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  where python >nul 2>&1
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY=python"
  )
)

if not defined PY (
  echo [错误] 未找到 Python 3.10+，请先安装并加入 PATH
  echo   https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [首次运行] 正在创建虚拟环境...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [错误] 创建虚拟环境失败
    pause
    exit /b 1
  )
)

set "REQ=studio\requirements.txt"
set "HASH_FILE=.venv\.studio_requirements.sha256"
set "NEED_INSTALL=1"

if exist "%HASH_FILE%" if exist "%REQ%" (
  powershell -NoProfile -Command ^
    "$h=(Get-FileHash -Algorithm SHA256 '%REQ%').Hash; $o=Get-Content '%HASH_FILE%' -ErrorAction SilentlyContinue; if($h -eq $o){exit 0}else{exit 1}" >nul 2>&1
  if not errorlevel 1 set "NEED_INSTALL=0"
)

if "%NEED_INSTALL%"=="1" (
  echo [安装] 检查 Studio 依赖（首次约需 5-15 分钟，PySide6 较大）...
  ".venv\Scripts\python.exe" -m pip install -q --upgrade pip
  ".venv\Scripts\pip.exe" install --default-timeout=120 -i https://pypi.tuna.tsinghua.edu.cn/simple -r %REQ%
  if errorlevel 1 (
    echo [重试] 换官方源再试一次...
    ".venv\Scripts\pip.exe" install --default-timeout=300 -r %REQ%
  )
  if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络后重试 start.cmd
    pause
    exit /b 1
  )
  powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 '%REQ%').Hash | Set-Content '%HASH_FILE%'" >nul 2>&1
) else (
  echo [跳过] 依赖未变更，直接启动（强制重装请运行 setup-studio.cmd）
)

echo [提示] 可选 OCR/YOLO: pip install paddleocr paddlepaddle ultralytics
echo [提示] 日常也可直接运行 run-studio.cmd（不检查依赖）
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
