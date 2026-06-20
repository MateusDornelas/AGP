@echo off
REM ===========================================================
REM  Otimizador de Rotas AGP - launcher backend + frontend
REM  - Backend: uvicorn (FastAPI) na porta 8000
REM  - Frontend: Vite (React) na porta 5173
REM  - Abre o navegador automaticamente
REM
REM  Recomenda-se executar via iniciar.vbs (sem janela visivel).
REM  Para debug, edite os helpers _backend.bat e _frontend.bat
REM  removendo /MIN abaixo para ver as janelas.
REM ===========================================================

setlocal
set "P=%~dp0"

REM ---- Backend (em janela minimizada) ----
start /MIN "" "%P%_backend.bat"

REM Aguarda 3s para o backend subir
timeout /t 3 /nobreak >nul

REM ---- Frontend (em janela minimizada) ----
start /MIN "" "%P%_frontend.bat"

REM Aguarda 6s para o Vite compilar e ficar pronto
timeout /t 6 /nobreak >nul

REM ---- Abre o navegador ----
start "" http://localhost:5173

endlocal
exit
