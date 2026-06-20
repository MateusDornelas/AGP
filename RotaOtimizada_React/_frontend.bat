@echo off
REM Helper interno: sobe Vite dev server (porta 5173).
REM NAO executar diretamente — usar iniciar.bat ou iniciar.vbs.

cd /d "%~dp0frontend"
call npm run dev

REM Se chegou aqui, Vite caiu — pausa pra mostrar erro.
echo.
echo *** Frontend encerrou. Pressione qualquer tecla para fechar. ***
pause >nul
