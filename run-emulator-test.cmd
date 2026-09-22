@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

rem Emulator smoke test: needs numpy/cv2/PySide6, so prefer .venv like run-studio.cmd.
rem Keep rem lines ASCII-only (see run-tests.cmd note about cmd.exe parsing).

set "PY=python"
if exist .venv\Scripts\python.exe set "PY=.venv\Scripts\python.exe"

"%PY%" tools\run_emulator_test.py
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo [hint] ModuleNotFoundError? run setup-studio.cmd to install deps
pause
endlocal & exit /b %RC%
