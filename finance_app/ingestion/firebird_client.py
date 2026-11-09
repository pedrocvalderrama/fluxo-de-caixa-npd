"""
Cliente de conexão estritamente READ-ONLY com o banco de dados Firebird do ERP Sisplan.
"""
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Tuple

try:
    import fdb
    FDB_INSTALADO = True
except ImportError:
    fdb = None
    FDB_INSTALADO = False

from finance_app.config.settings import settings

_api_loaded = False


def _garantir_api_carregada() -> None:
    """Carrega a DLL de 64 bits do Firebird 3 uma única vez."""
    global _api_loaded
    if not FDB_INSTALADO:
        raise ImportError(
            "A biblioteca 'fdb' não está instalada no ambiente Python. "
            "Execute: pip install fdb"
        )

    if _api_loaded:
        return

    dll_path = Path(settings.SISPLAN_CLIENT_DLL)
    if not dll_path.exists():
        raise FileNotFoundError(
            f"Client DLL do Firebird não encontrada em '{dll_path}'. "
            "Verifique o caminho configurado em SISPLAN_CLIENT_DLL."
        )

    fdb.load_api(str(dll_path))
    _api_loaded = True


TPB_MONITORAMENTO = bytes([
    fdb.isc_tpb_version3,
    fdb.isc_tpb_read,
    fdb.isc_tpb_read_committed,
    fdb.isc_tpb_rec_version,
    fdb.isc_tpb_nowait
]) if fdb else None


def testar_conexao_sisplan() -> Tuple[bool, str]:
    """
    Testa a conectividade com o banco Firebird do Sisplan com transação segura READ-ONLY.
    Retorna (sucesso, mensagem_ou_erro).
    """
    if not FDB_INSTALADO:
        return False, "Biblioteca 'fdb' não instalada no ambiente Python. Execute: pip install fdb"

    try:
        _garantir_api_carregada()
        conn = fdb.connect(
            host=settings.SISPLAN_HOST,
            port=settings.SISPLAN_PORT,
            database=settings.SISPLAN_DATABASE,
            user=settings.SISPLAN_USER,
            password=settings.SISPLAN_PASSWORD,
            charset="WIN1252",
        )
        tx = conn.trans(TPB_MONITORAMENTO) if TPB_MONITORAMENTO else conn
        cur = tx.cursor()
        cur.execute("SELECT 1 FROM RDB$DATABASE")
        cur.fetchone()
        if tx is not None and hasattr(tx, "commit"):
            tx.commit()
        conn.close()
        return True, f"Conexão ativa com {settings.SISPLAN_HOST}:{settings.SISPLAN_PORT}"
    except Exception as exc:
        return False, str(exc)


@contextmanager
def obter_conexao_sisplan() -> Generator:
    """
    Context manager que fornece transação estritamente para leitura com o banco Sisplan.
    Utiliza buffer TPB seguro (READ COMMITTED + REC_VERSION + READ ONLY) e garante
    execução de commit() e fechamento da conexão ao final.
    """
    if not FDB_INSTALADO:
        raise ImportError(
            "A biblioteca 'fdb' não está instalada no ambiente Python. "
            "Execute: pip install fdb"
        )

    _garantir_api_carregada()
    conn = None
    tx = None
    try:
        conn = fdb.connect(
            host=settings.SISPLAN_HOST,
            port=settings.SISPLAN_PORT,
            database=settings.SISPLAN_DATABASE,
            user=settings.SISPLAN_USER,
            password=settings.SISPLAN_PASSWORD,
            charset="WIN1252",
        )
        tx = conn.trans(TPB_MONITORAMENTO) if TPB_MONITORAMENTO else conn
        yield tx
    finally:
        if tx is not None and hasattr(tx, "commit"):
            try:
                tx.commit()
            except Exception:
                try:
                    tx.rollback()
                except Exception:
                    pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

