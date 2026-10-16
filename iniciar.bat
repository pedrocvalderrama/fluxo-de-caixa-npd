@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Fluxo de Caixa - Rede
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [AVISO] Ambiente ainda nao instalado.
    echo.
    echo Execute primeiro: instalar.bat
    echo.
    pause
    exit /b 1
)

if not exist "app.py" (
    echo [ERRO] app.py nao encontrado. Execute este BAT na pasta do projeto.
    pause
    exit /b 1
)

set "PORTA=8501"

echo ============================================================
echo   Iniciando Sistema de Gestao Financeira ^(acesso na rede^)
echo ============================================================
echo.
echo Pasta: %CD%
echo Porta: %PORTA%
echo.

REM Descobre IPs IPv4 da maquina (ignora 127.0.0.1)
echo Neste computador:
echo   http://localhost:%PORTA%
echo.
echo Em outros PCs da rede, abra no navegador:
set "ACHOU_IP=0"
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /R /C:"IPv4"') do (
    set "IP=%%A"
    set "IP=!IP: =!"
    if not "!IP!"=="127.0.0.1" (
        echo   http://!IP!:%PORTA%
        set "ACHOU_IP=1"
    )
)
if "!ACHOU_IP!"=="0" (
    echo   ^(nao foi possivel detectar o IP automaticamente^)
    echo   Use o IPv4 deste PC + :%PORTA%
)
echo.
echo IMPORTANTE:
echo   - Deixe esta janela aberta enquanto quiser que outros acessem
echo   - Se outro PC nao conectar, execute liberar-rede.bat
echo     ^(como Administrador^) uma vez, para liberar o Firewall
echo   - Para encerrar: Ctrl+C ou feche esta janela
echo ============================================================
echo.

"venv\Scripts\python.exe" -m streamlit run app.py --server.address 0.0.0.0 --server.port %PORTA%
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao iniciar. Tente rodar instalar.bat novamente.
    pause
    exit /b 1
)

endlocal
