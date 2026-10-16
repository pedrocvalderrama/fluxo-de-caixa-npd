@echo off
chcp 65001 >nul
setlocal EnableExtensions

title Liberar Firewall - Fluxo de Caixa
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
    echo Este script precisa ser executado como Administrador.
    echo.
    echo Clique com o botao direito em liberar-rede.bat
    echo e escolha: "Executar como administrador"
    echo.
    pause
    exit /b 1
)

set "PORTA=8501"
set "REGRA=Fluxo de Caixa Streamlit"

echo Liberando porta TCP %PORTA% no Firewall do Windows...
echo.

netsh advfirewall firewall delete rule name="%REGRA%" >nul 2>&1
netsh advfirewall firewall add rule name="%REGRA%" dir=in action=allow protocol=TCP localport=%PORTA% profile=private,domain

if errorlevel 1 (
    echo [ERRO] Nao foi possivel criar a regra do Firewall.
    pause
    exit /b 1
)

echo [OK] Regra criada: "%REGRA%"
echo     Porta liberada: %PORTA% ^(TCP entrada^)
echo.
echo Agora execute iniciar.bat e use o endereco http://IP-DESTE-PC:%PORTA%
echo nos outros computadores da rede.
echo.
pause
endlocal
