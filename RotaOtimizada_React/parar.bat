@echo off
REM ===========================================================
REM  Otimizador de Rotas AGP - desligar backend + frontend
REM  Mata os processos nas portas 8000 (FastAPI) e 5173 (Vite).
REM ===========================================================

echo Parando backend (porta 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

echo Parando frontend (porta 5173)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

echo.
echo Servicos encerrados.
timeout /t 2 /nobreak >nul
