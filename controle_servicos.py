"""
Gerenciador e controlador dos serviços em segundo plano do Fluxo de Caixa.

Comandos suportados:
  python controle_servicos.py status   -> Exibe o status do Streamlit e da Automação
  python controle_servicos.py iniciar  -> Inicia os serviços em segundo plano (se não estiverem rodando)
  python controle_servicos.py parar    -> Encerra os serviços em segundo plano com segurança
  python controle_servicos.py reiniciar-> Reinicia os serviços
"""
from __future__ import annotations

import sys
import os
import time
import socket
import subprocess
from datetime import datetime
import psutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

VENV_DIR = os.path.join(BASE_DIR, "venv")
PYTHON_EXE = os.path.join(VENV_DIR, "Scripts", "python.exe")
PYTHONW_EXE = os.path.join(VENV_DIR, "Scripts", "pythonw.exe")

STREAMLIT_PORT = 8501
AUTOMACAO_PORT = 49215


def is_port_in_use(port: int) -> bool:
    """Verifica se uma porta local está aberta e aceitando conexões."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def obter_processos_projeto() -> dict[str, list[psutil.Process]]:
    """Identifica os processos ativos específicos do projeto FLUXO DE CAIXA."""
    procs = {"streamlit": [], "automacao": []}
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = p.info["cmdline"]
            if not cmdline:
                continue
            cmd_str = " ".join(cmdline).lower()

            # Processos pertencentes a este projeto
            if "fluxo de caixa" in cmd_str or (p.cwd() and "fluxo de caixa" in p.cwd().lower()):
                if "streamlit" in cmd_str:
                    procs["streamlit"].append(p)
                elif "automacao.py" in cmd_str:
                    procs["automacao"].append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return procs


def iniciar_servicos() -> None:
    """Inicia o Streamlit e a Automação em segundo plano (invisível, sem janelas)."""
    procs = obter_processos_projeto()

    # 1. Iniciar Streamlit se não estiver ativo
    porta_ativa = is_port_in_use(STREAMLIT_PORT)
    if procs["streamlit"] or porta_ativa:
        print(f"[OK] Streamlit já está em execução (Porta {STREAMLIT_PORT}).")
    else:
        print("[...] Iniciando Streamlit em segundo plano...")
        cmd_streamlit = [
            PYTHONW_EXE,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.address",
            "0.0.0.0",
            "--server.port",
            str(STREAMLIT_PORT),
            "--server.headless",
            "true",
            "--browser.serverAddress",
            "localhost",
        ]
        # Flags para desanexar do terminal atual no Windows
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            cmd_streamlit,
            cwd=BASE_DIR,
            creationflags=creationflags,
            close_fds=True,
        )
        print(f"[OK] Streamlit iniciado com sucesso em http://localhost:{STREAMLIT_PORT}")

    # 2. Iniciar Automação se não estiver ativa
    if procs["automacao"]:
        print("[OK] Serviço de Automação já está em execução.")
    else:
        print("[...] Iniciando Serviço de Automação em segundo plano...")
        cmd_automacao = [PYTHONW_EXE, "automacao.py"]
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            cmd_automacao,
            cwd=BASE_DIR,
            creationflags=creationflags,
            close_fds=True,
        )
        print("[OK] Serviço de Automação iniciado com sucesso.")


def parar_servicos() -> None:
    """Encerra com segurança todos os processos em segundo plano do projeto."""
    print("Localizando processos em execução do Fluxo de Caixa...")
    procs = obter_processos_projeto()
    total = len(procs["streamlit"]) + len(procs["automacao"])

    if total == 0 and not is_port_in_use(STREAMLIT_PORT):
        print("Nenhum serviço do Fluxo de Caixa estava em execução.")
        return

    for grupo, lista in procs.items():
        for p in lista:
            try:
                print(f"Encerrando {grupo} (PID {p.pid})...")
                p.terminate()
            except Exception:
                pass

    # Aguarda término gracioso
    time.sleep(1.0)

    # Força encerramento caso algum ainda persista
    for grupo, lista in procs.items():
        for p in lista:
            try:
                if p.is_running():
                    p.kill()
            except Exception:
                pass

    print("[OK] Todos os serviços em segundo plano foram finalizados.")


def exibir_status() -> None:
    """Exibe o diagnóstico e status atual dos serviços."""
    procs = obter_processos_projeto()
    porta_ativa = is_port_in_use(STREAMLIT_PORT)

    print("=" * 60)
    print("  STATUS DOS SERVIÇOS - FLUXO DE CAIXA")
    print("=" * 60)

    # Streamlit
    if procs["streamlit"] or porta_ativa:
        pids = [str(p.pid) for p in procs["streamlit"]]
        pids_str = f" (PIDs: {', '.join(pids)})" if pids else ""
        print(f"  Streamlit (Web App):  [RODANDO] http://localhost:{STREAMLIT_PORT}{pids_str}")
    else:
        print("  Streamlit (Web App):  [PARADO]")

    # Automação
    if procs["automacao"]:
        pids = [str(p.pid) for p in procs["automacao"]]
        print(f"  Automação (2h / 12h): [RODANDO] (PIDs: {', '.join(pids)})")
    else:
        print("  Automação (2h / 12h): [PARADA]")

    print("-" * 60)

    # Metadados do banco SQLite
    try:
        from finance_app.database.connection import get_meta
        hb = get_meta("automacao_heartbeat") or "Sem registro"
        db_sync = get_meta("automacao_db_ultimo_sucesso") or "Sem registro"
        db_res = get_meta("automacao_db_resumo") or ""
        sd_sync = get_meta("automacao_saldo_ultimo_sucesso") or "Sem registro"
        sd_res = get_meta("automacao_saldo_resumo") or ""

        print(f"  Último batimento (Heartbeat): {hb}")
        print(f"  Última sincronização Sisplan:  {db_sync} ({db_res})")
        print(f"  Último saldo diário Excel:    {sd_sync} ({sd_res})")
    except Exception as exc:
        print(f"  Não foi possível ler metadados do banco: {exc}")

    print("=" * 60)


if __name__ == "__main__":
    acao = sys.argv[1].lower() if len(sys.argv) > 1 else "status"

    if acao == "iniciar":
        iniciar_servicos()
    elif acao == "parar":
        parar_servicos()
    elif acao == "reiniciar":
        parar_servicos()
        time.sleep(1)
        iniciar_servicos()
    elif acao == "status":
        exibir_status()
    else:
        print(f"Uso: python controle_servicos.py [status | iniciar | parar | reiniciar]")
