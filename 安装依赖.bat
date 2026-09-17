@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在准备 Clinical Trial AI Assistant...
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo 未找到 Python。请先从 https://www.python.org/downloads/ 安装 Python 3.11 或更高版本。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
".venv\Scripts\python.exe" scripts\generate_sample_data.py
echo.
echo 安装完成。以后双击“启动项目.bat”即可。
pause
