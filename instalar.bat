@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Instalacao - Sistema de Gestao Financeira
cd /d "%~dp0"

echo ============================================================
echo   Instalacao automatica - Fluxo de Caixa
echo ============================================================
echo.
echo Pasta do projeto:
echo   %CD%
echo.

REM ---- 1) Localizar Python -------------------------------------------------
set "PYTHON_CMD="

where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 -c "import sys" >nul 2>&1 && set "PYTHON_CMD=py -3.12"
    if not defined PYTHON_CMD (
        py -3.11 -c "import sys" >nul 2>&1 && set "PYTHON_CMD=py -3.11"
    )
    if not defined PYTHON_CMD (
        py -3.10 -c "import sys" >nul 2>&1 && set "PYTHON_CMD=py -3.10"
    )
    if not defined PYTHON_CMD (
        py -3 -c "import sys" >nul 2>&1 && set "PYTHON_CMD=py -3"
    )
)

if not defined PYTHON_CMD (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo [ERRO] Python nao encontrado neste computador.
    echo.
    echo Instale o Python 3.10 ou superior em:
    echo   https://www.python.org/downloads/
    echo.
    echo Na instalacao, marque a opcao:
    echo   "Add python.exe to PATH"
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado: %PYTHON_CMD%
%PYTHON_CMD% -c "import sys; print('     Versao:', sys.version.split()[0]); raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo [ERRO] E necessario Python 3.10 ou superior.
    pause
    exit /b 1
)
echo.

REM ---- 2) Verificar requirements.txt --------------------------------------
if not exist "requirements.txt" (
    echo [ERRO] Arquivo requirements.txt nao encontrado nesta pasta.
    pause
    exit /b 1
)
if not exist "app.py" (
    echo [ERRO] Arquivo app.py nao encontrado. Execute este BAT na pasta do projeto.
    pause
    exit /b 1
)

REM ---- 3) Criar ambiente virtual ------------------------------------------
if not exist "venv\Scripts\python.exe" (
    echo [..] Criando ambiente virtual em .\venv ...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado.
) else (
    echo [OK] Ambiente virtual ja existe.
)
echo.

set "VENV_PY=%CD%\venv\Scripts\python.exe"
set "VENV_PIP=%CD%\venv\Scripts\pip.exe"

if not exist "%VENV_PY%" (
    echo [ERRO] Python do venv nao encontrado em:
    echo   %VENV_PY%
    pause
    exit /b 1
)

REM ---- 4) Atualizar pip e instalar dependencias ---------------------------
echo [..] Atualizando pip...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [AVISO] Nao foi possivel atualizar o pip. Continuando mesmo assim...
)
echo.

echo [..] Instalando dependencias de requirements.txt ...
echo     Isso pode levar alguns minutos na primeira vez.
echo.
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao instalar as dependencias.
    echo Verifique sua conexao com a internet e tente novamente.
    pause
    exit /b 1
)

REM ---- 5) Garantir pastas de dados ----------------------------------------
if not exist "data" mkdir "data"
if not exist "data\backups" mkdir "data\backups"

echo.
echo ============================================================
echo   Instalacao concluida com sucesso!
echo ============================================================
echo.
echo Para iniciar o sistema, use:
echo   iniciar.bat
echo.
echo Ou execute manualmente:
echo   venv\Scripts\streamlit run app.py
echo.

choice /C SN /M "Deseja iniciar o sistema agora (S/N)"
if errorlevel 2 goto fim
if errorlevel 1 goto iniciar

:iniciar
echo.
echo [..] Abrindo o sistema no navegador...
echo     (Feche esta janela ou pressione Ctrl+C para encerrar)
echo.
"%VENV_PY%" -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
goto fim

:fim
echo.
pause
endlocal
