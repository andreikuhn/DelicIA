@echo off
REM Abre o site DelicIA em http://localhost:8505
REM Roda numa janela minimizada e, se o site parar, ele reinicia sozinho.
REM Para desligar: dois cliques em parar_site.bat
cd /d "%~dp0"
if not "%~1"=="servidor" (
  if exist parar.flag del parar.flag
  start "DelicIA - servidor - NAO FECHE" /min "%~f0" servidor
  echo Site iniciando em segundo plano. Em uns 20 segundos abra http://localhost:8505
  timeout /t 5 >nul
  exit /b
)
title DelicIA - servidor (NAO FECHE esta janela)
:loop
if exist parar.flag goto fim
echo [%date% %time%] site iniciando >> servidor.log
python -m streamlit run app.py --server.port 8505 --server.headless true --server.fileWatcherType none >> servidor.log 2>&1
echo [%date% %time%] o site parou (codigo %errorlevel%) >> servidor.log
if exist parar.flag goto fim
timeout /t 3 /nobreak >nul
goto loop
:fim
del parar.flag 2>nul
exit
