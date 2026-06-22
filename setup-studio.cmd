@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  python -m venv .venv
)
.venv\Scripts\pip install -r studio\requirements.txt
if exist ..\adb-ide\requirements.txt (
  echo 安装 adb-ide 依赖（IDE 识图/YOLO/OCR 与 adb-ide 相同）…
  .venv\Scripts\pip install -r ..\adb-ide\requirements.txt
) else (
  echo 警告: 未找到 ..\adb-ide\requirements.txt，请先 clone adb-ide 到同级目录
)
echo.
echo 安装完成。需 adb-ide 在: %~dp0..\adb-ide
echo 运行 run-studio.cmd 启动 Studio（界面与 adb-ide 相同 + 打包 APK）
