@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===============================================
echo   双界录 · 都市心动  AI 文游
echo   http://127.0.0.1:8000
echo   改动 app/ 或 static/ 下的文件会自动重载
echo   关闭本窗口即停止服务
echo ===============================================
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
