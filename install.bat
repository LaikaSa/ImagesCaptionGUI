@echo off
setlocal EnableDelayedExpansion
echo Setting up Image Caption System...

:: Check if git is installed
where git >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Git is not installed. Please install Git first.
    pause
    exit /b 1
)

:: Initialize and update submodules
echo Initializing TabbyAPI submodule...
git submodule update --init --recursive

:: Create a temporary batch file for TabbyAPI installation
echo @echo off > install_tabby.bat
echo cd backend >> install_tabby.bat
echo python -m venv venv >> install_tabby.bat
echo call venv\Scripts\activate >> install_tabby.bat
echo start "TabbyAPI Server" /wait cmd /c "python start.py ^& timeout /t 30 ^& taskkill /F /PID %%PID%%" >> install_tabby.bat
echo exit >> install_tabby.bat

:: Run TabbyAPI installation first
echo Installing TabbyAPI...
start "TabbyAPI Installation" /wait cmd /c install_tabby.bat

:: Clean up TabbyAPI installation batch
del install_tabby.bat

:: Create and run GUI installation after TabbyAPI is done
echo @echo off > install_gui.bat
echo python -m venv venv >> install_gui.bat
echo call venv\Scripts\activate >> install_gui.bat
echo pip install -r requirements.txt >> install_gui.bat
echo echo GUI installation complete. >> install_gui.bat
echo del install_gui.bat >> install_gui.bat

echo Installing GUI...
start /wait cmd /c install_gui.bat

echo.
echo Installation completed!
echo To start the application:
echo 1. First run the backend using 'backend\start.bat'
echo 2. Then run the GUI using 'run.bat'
echo.
pause