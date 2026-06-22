@echo off
cd /d "%~dp0"
python -m venv .venv
.venv\Scripts\pip install -r studio\requirements.txt
echo 安装完成。运行 run-studio.cmd 启动 Studio。
