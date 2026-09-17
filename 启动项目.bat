@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 请先双击“安装依赖.bat”。
  pause
  exit /b 1
)
start "" http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501
pause
