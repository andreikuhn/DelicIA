@echo off
REM Desliga o site DelicIA (e impede que ele reinicie sozinho)
cd /d "%~dp0"
echo parar > parar.flag
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8505" ^| findstr "LISTENING"') do taskkill /PID %%p /F >nul 2>&1
echo Site desligado.
timeout /t 3 >nul
