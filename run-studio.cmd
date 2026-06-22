@echo off
cd /d "%~dp0studio"
if exist ..\.venv\Scripts\python.exe (
  ..\.venv\Scripts\python.exe -m studio.main
) else (
  python -m studio.main
)
