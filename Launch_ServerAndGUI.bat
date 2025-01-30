@echo off
setlocal

:: Start TabbyAPI backend in a new window
start "TabbyAPI Backend" cmd /k "cd backend && start.bat"

echo Waiting for TabbyAPI to initialize...

:check_loop
:: Check if the server is responding
curl -s http://127.0.0.1:5000/health | findstr /C:"healthy" >nul
if %ERRORLEVEL%==0 (
    echo TabbyAPI is ready! Starting GUI...
    goto start_gui
)
timeout /t 2 /nobreak >nul
goto check_loop

:start_gui
call venv\Scripts\activate
python main.py

endlocal