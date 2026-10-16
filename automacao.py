"""
Serviço de Automação em Segundo Plano do Sistema de Fluxo de Caixa.

Responsabilidades:
1. Sincronização do Banco de Dados (Sisplan SQL):
   - Executa a cada 2 horas (e na inicialização do sistema).
   - Extrai Contas a Pagar e Contas a Receber e atualiza o banco SQLite local.
2. Atualização do Saldo do Dia (Excel Financeiro):
   - Executa diariamente às 12h:00 (e na inicialização se ainda não registrado no dia).
   - Lê a planilha da rede e atualiza os saldos bancários oficiais.
3. Execução silenciosa e contínua em segundo plano com tolerância a falhas de rede.
"""
from __future__ import annotations

import sys
import os
import time
import socket
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, date, timedelta

# Garante que a pasta raiz do projeto está no sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from finance_app.database.connection import SessionLocal, init_db, get_meta, set_meta
from finance_app.database.models import SaldoDiario
from finance_app.ingestion.firebird_client import testar_conexao_sisplan
from finance_app.ingestion.firebird_extractor import extrair_receber_sisplan, extrair_pagar_sisplan
from finance_app.ingestion.importer import sincronizar_movimentacoes_normalizadas
from finance_app.services.saldo_service import ler_e_atualizar_saldo_excel, DEFAULT_SALDO_EXCEL_PATH

# Configuração de Logs
LOG_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "automacao.log")

logger = logging.getLogger("automacao")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%d/%m/%Y %H:%M:%S")

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Porta usada para garantir que apenas UMA instância rode por vez
LOCK_PORT = 49215
_lock_socket = None


def garantir_instancia_unica() -> bool:
    """Garante via socket local que apenas uma instância da automação esteja ativa."""
    global _lock_socket
    try:
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(("127.0.0.1", LOCK_PORT))
        return True
    except socket.error:
        logger.warning("Outra instância de automação já está em execução nesta máquina. Finalizando.")
        return False


def executar_sincronizacao_banco() -> bool:
    """Executa a sincronização completa do Contas a Pagar e Receber via Sisplan SQL."""
    logger.info("Iniciando sincronização periódica do banco de dados (Sisplan SQL)...")
    conectado, msg = testar_conexao_sisplan()
    if not conectado:
        logger.warning(f"Sisplan indisponível no momento: {msg}. Tentará novamente no próximo ciclo.")
        set_meta("automacao_db_status", f"Falha de conexão: {msg}")
        return False

    try:
        hoje = date.today()
        # Sincroniza todo o ano vigente
        dt_inicio = date(hoje.year, 1, 1)
        dt_fim = date(hoje.year, 12, 31)

        logger.info(f"Consultando Sisplan no período de {dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}...")
        movs_rec = extrair_receber_sisplan(
            data_inicio=dt_inicio,
            data_fim=dt_fim,
            emp_id=None,
            apenas_duplicatas=True,
            filtrar_devolucoes=True,
        )
        movs_pag = extrair_pagar_sisplan(
            data_inicio=dt_inicio,
            data_fim=dt_fim,
            emp_id=None,
            apenas_ap=True,
        )
        movs_total = movs_rec + movs_pag

        logger.info(f"Registros extraídos do Sisplan: {len(movs_rec)} a receber + {len(movs_pag)} a pagar = {len(movs_total)} total.")

        with SessionLocal() as session:
            resultado = sincronizar_movimentacoes_normalizadas(
                movs_total,
                session,
                nome_origem="Automação Sisplan SQL (Agendada)",
                callback_progresso=None,
            )

        agora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        resumo_str = f"{resultado.total_importados} novos, {resultado.total_atualizados} atualizados, {resultado.total_ja_existentes} mantidos"
        set_meta("automacao_db_ultimo_sucesso", agora_str)
        set_meta("automacao_db_status", "OK")
        set_meta("automacao_db_resumo", resumo_str)

        logger.info(f"Sincronização do banco concluída com sucesso! ({resumo_str})")
        return True
    except Exception as exc:
        logger.error(f"Erro ao sincronizar banco de dados: {exc}", exc_info=True)
        set_meta("automacao_db_status", f"Erro: {exc}")
        return False


def executar_atualizacao_saldo(origem: str = "Agendamento") -> bool:
    """Executa a atualização do saldo bancário diário a partir do arquivo Excel."""
    logger.info(f"Iniciando atualização do saldo do dia [{origem}]...")
    if not os.path.exists(DEFAULT_SALDO_EXCEL_PATH):
        logger.warning(f"Arquivo de saldo na rede não encontrado: {DEFAULT_SALDO_EXCEL_PATH}. Tentará novamente.")
        set_meta("automacao_saldo_status", "Arquivo não encontrado na rede")
        return False

    try:
        with SessionLocal() as session:
            res = ler_e_atualizar_saldo_excel(caminho_arquivo=DEFAULT_SALDO_EXCEL_PATH, session=session)

        agora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        data_saldo_str = res["data"].strftime("%d/%m/%Y")
        total_str = f"R$ {res['total_geral']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        resumo = f"Data: {data_saldo_str} | Total: {total_str}"

        set_meta("automacao_saldo_ultimo_sucesso", agora_str)
        set_meta("automacao_saldo_status", "OK")
        set_meta("automacao_saldo_resumo", resumo)

        logger.info(f"Saldo diário atualizado com sucesso! Data: {data_saldo_str}, Total: {total_str}")
        return True
    except Exception as exc:
        logger.error(f"Erro ao atualizar saldo diário: {exc}", exc_info=True)
        set_meta("automacao_saldo_status", f"Erro: {exc}")
        return False


def verificar_saldo_hoje_existe() -> bool:
    """Verifica se o saldo de hoje já foi importado no banco local."""
    hoje = date.today()
    try:
        with SessionLocal() as session:
            count = session.query(SaldoDiario).filter(SaldoDiario.data == hoje).count()
            return count >= 8
    except Exception:
        return False


def loop_principal():
    """Loop contínuo de monitoramento e execução dos agendamentos."""
    logger.info("=== Serviço de Automação de Fluxo de Caixa Iniciado ===")
    logger.info(f"Diretório base: {BASE_DIR}")
    logger.info(f"Arquivo de log: {LOG_FILE}")
    logger.info("Configuração: Banco de dados a cada 2 horas | Saldo diário às 12:00")

    init_db()

    # Intervalos
    INTERVALO_BANCO_SEGUNDOS = 2 * 60 * 60  # 2 horas
    ultimo_banco_sync = datetime.min
    ultimo_saldo_data_executada = None

    # Execução inicial imediata do banco de dados ao iniciar
    logger.info("Executando primeira sincronização do banco de dados na inicialização...")
    if executar_sincronizacao_banco():
        ultimo_banco_sync = datetime.now()

    while True:
        try:
            agora = datetime.now()
            hoje = agora.date()

            # Atualiza batimento cardíaco da automação no banco
            set_meta("automacao_heartbeat", agora.strftime("%d/%m/%Y %H:%M:%S"))

            # 1. Sincronização do Banco a cada 2 horas
            tempo_desde_ultimo = (agora - ultimo_banco_sync).total_seconds()
            if tempo_desde_ultimo >= INTERVALO_BANCO_SEGUNDOS:
                logger.info(f"Disparo periódico: 2 horas decorridas desde o último sync ({tempo_desde_ultimo:.0f}s).")
                if executar_sincronizacao_banco():
                    ultimo_banco_sync = agora
                else:
                    # Em caso de falha de conexão, tenta novamente em 15 minutos em vez de esperar 2 horas
                    ultimo_banco_sync = agora - timedelta(seconds=INTERVALO_BANCO_SEGUNDOS - 15 * 60)

            # 2. Atualização do Saldo às 12:00 (am / meio-dia)
            # Dispara se for 12:00 ou posterior e ainda não tiver executado hoje
            if agora.hour >= 12 and ultimo_saldo_data_executada != hoje:
                logger.info("Horário das 12:00 atingido. Disparando atualização do saldo diário...")
                if executar_atualizacao_saldo(origem="Agendamento 12:00"):
                    ultimo_saldo_data_executada = hoje
                else:
                    # Em caso de erro temporário (ex: planilha aberta), tentará em 10 minutos
                    pass

            # Dorme por 30 segundos entre verificações
            time.sleep(30)

        except KeyboardInterrupt:
            logger.info("Serviço de automação finalizado pelo usuário (Ctrl+C).")
            break
        except Exception as exc:
            logger.error(f"Erro inesperado no loop da automação: {exc}", exc_info=True)
            time.sleep(30)


if __name__ == "__main__":
    if not garantir_instancia_unica():
        sys.exit(0)

    # Suporte a execução manual direta: python automacao.py --exec-now
    if "--exec-now" in sys.argv:
        print("Executando sincronização imediata do banco e saldo...")
        executar_sincronizacao_banco()
        executar_atualizacao_saldo(origem="Manual --exec-now")
        print("Concluído.")
        sys.exit(0)

    loop_principal()
