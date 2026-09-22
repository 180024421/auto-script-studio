@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

rem Run the Studio unit tests. Extra args go straight to pytest, e.g.:
rem   run-tests.cmd -k layout
rem   run-tests.cmd tests\test_packager_validate.py -v
rem
rem NOTE: keep rem lines ASCII-only. cmd.exe parses batch files under the OEM
rem codepage, and UTF-8 multibyte text inside a rem line desyncs the parser --
rem the comment body then gets executed as commands (reproduced with PySide6 /
rem Windows 11). Chinese is fine in plain echo lines, see start.cmd.

set "PY=python"
if exist .venv\Scripts\python.exe set "PY=.venv\Scripts\python.exe"

"%PY%" -m pytest tests %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo [hint] ModuleNotFoundError? run setup-studio.cmd to install pytest
endlocal & exit /b %RC%
