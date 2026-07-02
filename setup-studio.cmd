@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  echo 创建虚拟环境...
  python -m venv .venv
)

echo 安装 Studio 依赖...
.venv\Scripts\python.exe -m pip install -q --upgrade pip
.venv\Scripts\pip.exe install --default-timeout=120 -i https://pypi.tuna.tsinghua.edu.cn/simple -r studio\requirements.txt
if errorlevel 1 (
  .venv\Scripts\pip.exe install --default-timeout=300 -r studio\requirements.txt
)

echo.
echo 安装完成。运行 start.cmd 或 run-studio.cmd 启动 Studio。
echo 可选识字/YOLO 测试: pip install paddleocr paddlepaddle ultralytics
endlocal
