@echo off
REM Roda todos os testes automatizados do DelicIA e guarda o resultado em resultado_testes.txt
cd /d "%~dp0"
python -m pytest -v > resultado_testes.txt 2>&1
type resultado_testes.txt
echo.
echo Resultado completo salvo em resultado_testes.txt
pause
