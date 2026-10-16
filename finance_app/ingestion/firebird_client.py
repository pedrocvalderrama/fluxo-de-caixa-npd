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


def testar_conexao_sisplan() -> Tuple[bool, str]:
    """
    Testa a conectividade com o banco Firebird do Sisplan.
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
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM RDB$DATABASE")
        cur.fetchone()
        conn.close()
        return True, f"Conexão ativa com {settings.SISPLAN_HOST}:{settings.SISPLAN_PORT}"
    except Exception as exc:
        return False, str(exc)


@contextmanager
def obter_conexao_sisplan() -> Generator:
    """
    Context manager que fornece conexão estritamente para leitura com o banco Sisplan.
    Garante fechamento da conexão após o uso.
    """
    if not FDB_INSTALADO:
        raise ImportError(
            "A biblioteca 'fdb' não está instalada no ambiente Python. "
            "Execute: pip install fdb"
        )

    _garantir_api_carregada()
    conn = None
    try:
        conn = fdb.connect(
            host=settings.SISPLAN_HOST,
            port=settings.SISPLAN_PORT,
            database=settings.SISPLAN_DATABASE,
            user=settings.SISPLAN_USER,
            password=settings.SISPLAN_PASSWORD,
            charset="WIN1252",
        )
        yield conn
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
