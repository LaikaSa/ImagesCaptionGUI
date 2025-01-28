@echo off
set CUDA_VISIBLE_DEVICES=1
setlocal

:: Start TabbyAPI backend in a new window
start "TabbyAPI Backend" cmd /k "cd backend\tabbyAPI && start.bat"

:: Wait for backend to initialize (adjust time if needed)
timeout /t 10 /nobreak

:: Start GUI
call venv\Scripts\activate
python src/main.py

endlocal