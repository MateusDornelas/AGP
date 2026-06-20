@echo off
REM ===========================================================
REM  Otimizador AGP - setup de dependencias (rodar 1x apenas)
REM  Instala fastapi/uvicorn no .venv e React/Vite no frontend.
REM ===========================================================

setlocal

set "PROJ_ROOT=%~dp0"
set "VENV_PY=%PROJ_ROOT%..\.venv\Scripts\python.exe"
set "BACKEND_REQ=%PROJ_ROOT%backend\requirements.txt"
set "FRONTEND_DIR=%PROJ_ROOT%frontend"

echo.
echo === [1/2] Instalando dependencias do backend (Python) ===
"%VENV_PY%" -m pip install -r "%BACKEND_REQ%"
if errorlevel 1 (
    echo ERRO no pip install. Verifique se o .venv existe em ..\.venv
    pause
    exit /b 1
)

echo.
echo === [2/2] Instalando dependencias do frontend (npm) ===
cd /d "%FRONTEND_DIR%"
call npm install
if errorlevel 1 (
    echo ERRO no npm install. Confira se Node.js esta instalado.
    pause
    exit /b 1
)

echo.
echo ===========================================================
echo  Setup concluido! Agora pode usar iniciar.vbs normalmente.
echo ===========================================================
pause
