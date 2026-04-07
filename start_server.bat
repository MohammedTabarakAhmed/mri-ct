@echo off
cd /d "%~dp0"
call "C:\Users\Moham\anaconda3\Scripts\activate.bat" medai
start "" "http://127.0.0.1:8003"
python -m uvicorn api.app:app --host 127.0.0.1 --port 8003