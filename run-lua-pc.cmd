@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: run-lua-pc.cmd PROJECT_DIR [ADB_SERIAL]
  exit /b 1
)
set "PROJ=%~1"
set "SERIAL=%~2"
if exist .venv\Scripts\python.exe (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)
if "%SERIAL%"=="" (
  "%PY%" -m studio.runtime.lua_runner "%PROJ%"
) else (
  "%PY%" -m studio.runtime.lua_runner "%PROJ%" --serial "%SERIAL%"
)
