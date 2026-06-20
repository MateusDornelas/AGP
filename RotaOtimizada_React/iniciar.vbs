' ===========================================================
'  Otimizador de Rotas AGP - launcher 100% SILENCIOSO
'
'  Sobe backend (FastAPI/uvicorn :8000) e frontend (Vite :5173)
'  COMPLETAMENTE OCULTOS — nada aparece na barra de tarefas.
'
'  Para debugar (ver janelas), use iniciar.bat em vez deste.
'  Para parar tudo, use parar.bat.
' ===========================================================

Set WshShell = CreateObject("WScript.Shell")
Set objFSO   = CreateObject("Scripting.FileSystemObject")

strFolder = objFSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strFolder

' WshShell.Run(comando, windowStyle, waitOnReturn)
'   windowStyle = 0  -> janela completamente oculta (sem taskbar)
'   waitOnReturn = False -> nao bloqueia, segue tocando o proximo passo

' 1) Backend (FastAPI/uvicorn)
WshShell.Run "cmd /c """ & strFolder & "\_backend.bat""", 0, False

' Aguarda 3s para o backend subir
WScript.Sleep 3000

' 2) Frontend (Vite dev server)
WshShell.Run "cmd /c """ & strFolder & "\_frontend.bat""", 0, False

' Aguarda 6s para o Vite compilar
WScript.Sleep 6000

' 3) Abre o navegador no front (windowStyle=1 = normal)
WshShell.Run "http://localhost:5173", 1, False

Set WshShell = Nothing
Set objFSO   = Nothing
