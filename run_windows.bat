@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY (where python >nul 2>nul && set PY=python)
if not defined PY (
  echo Python not found. Please install Python 3.9+ from https://www.python.org/downloads/ and check "Add Python to PATH".
  pause
  exit /b 1
)
%PY% -c "import ooz" 2>nul || (
  echo Installing Oodle decompressor pyooz ...
  %PY% -m pip install --user vendor\pyooz-0.0.8-cp38-abi3-win_amd64.whl || %PY% -m pip install --user pyooz
)
%PY% woth_scanner.py
pause
