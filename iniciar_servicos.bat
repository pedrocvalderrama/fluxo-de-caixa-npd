@echo off
chcp 65001 > nul
cd /d "C:\dev\FLUXO DE CAIXA"
echo ============================================================
echo   Iniciando Servicos em Segundo Plano - Fluxo de Caixa
echo ============================================================
echo.
"venv\Scripts\python.exe" controle_servicos.py iniciar
echo.
"venv\Scripts\python.exe" controle_servicos.py status
echo.
pause
