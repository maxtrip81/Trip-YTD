@echo off
rem Trip YTD per Windows: avvia il server locale, apre la pagina nel browser
rem e crea i collegamenti "Trip YTD" sul Desktop e nel menu Start.
set "ROOT=%~dp0"
if not exist "%ROOT%runtime\pythonw.exe" (
  echo Trip YTD non trova la cartella "runtime".
  echo Estrai TUTTO il file zip in una cartella e poi avvia di nuovo "Avvia Trip YTD".
  pause
  exit /b 1
)
start "" "%ROOT%runtime\pythonw.exe" "%ROOT%app\trip_ytd.py" --shortcuts
