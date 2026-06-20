@echo off
REM Helper interno: sobe FastAPI/Uvicorn (porta 8000).
REM NAO executar diretamente — usar iniciar.bat ou iniciar.vbs.

cd /d "%~dp0backend"
"%~dp0..\.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000

REM Se chegou aqui, uvicorn caiu — pausa pra mostrar erro.
echo.
echo *** Backend encerrou. Pressione qualquer tecla para fechar. ***
pause >nul
