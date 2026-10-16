@echo off
chcp 65001 > nul
cd /d "C:\dev\FLUXO DE CAIXA"
"venv\Scripts\python.exe" controle_servicos.py status
echo.
pause
