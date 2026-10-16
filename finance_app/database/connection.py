"""
Configurações de conexão e gerenciamento de sessões do SQLAlchemy.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from finance_app.config.settings import settings

# Garante que os diretórios necessários existem
settings.ensure_dirs()

# Criação da engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

# Configurações específicas para SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager para fornecer uma sessão do banco de dados.
    Garante que a sessão seja fechada ao final do uso.
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def _tabela_existe(conn, nome: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": nome},
    ).fetchone()
    return row is not None


def _coluna_existe(conn, tabela: str, coluna: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({tabela})")).fetchall()
    return coluna in {r[1] for r in rows}


def _migrar_schema() -> None:
    """Aplica colunas novas em bancos SQLite já existentes (create_all não altera tabelas)."""
    with engine.begin() as conn:
        if _tabela_existe(conn, "movimentacoes") and not _coluna_existe(conn, "movimentacoes", "banco_id"):
            conn.execute(text("ALTER TABLE movimentacoes ADD COLUMN banco_id INTEGER"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mov_banco ON movimentacoes(banco_id)"))
        if _tabela_existe(conn, "movimentacoes") and not _coluna_existe(conn, "movimentacoes", "documento"):
            conn.execute(text("ALTER TABLE movimentacoes ADD COLUMN documento VARCHAR(100)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mov_documento ON movimentacoes(documento)"))
        if _tabela_existe(conn, "movimentacoes_raw") and not _coluna_existe(conn, "movimentacoes_raw", "banco_original"):
            conn.execute(text("ALTER TABLE movimentacoes_raw ADD COLUMN banco_original VARCHAR(100)"))
        if _tabela_existe(conn, "movimentacoes_raw") and not _coluna_existe(conn, "movimentacoes_raw", "documento_original"):
            conn.execute(text("ALTER TABLE movimentacoes_raw ADD COLUMN documento_original VARCHAR(100)"))
        if not _tabela_existe(conn, "app_meta"):
            conn.execute(text(
                "CREATE TABLE app_meta (chave VARCHAR(100) PRIMARY KEY, valor VARCHAR(200))"
            ))


def _meta_get(conn, chave: str) -> str | None:
    if not _tabela_existe(conn, "app_meta"):
        return None
    row = conn.execute(
        text("SELECT valor FROM app_meta WHERE chave = :c"),
        {"c": chave},
    ).fetchone()
    return row[0] if row else None


def _meta_set(conn, chave: str, valor: str) -> None:
    conn.execute(
        text(
            "INSERT INTO app_meta (chave, valor) VALUES (:c, :v) "
            "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor"
        ),
        {"c": chave, "v": valor},
    )


def get_meta(chave: str) -> str | None:
    """Retorna o valor de uma chave na tabela app_meta."""
    with engine.begin() as conn:
        return _meta_get(conn, chave)


def set_meta(chave: str, valor: str) -> None:
    """Salva ou atualiza uma chave na tabela app_meta."""
    with engine.begin() as conn:
        if not _tabela_existe(conn, "app_meta"):
            conn.execute(text(
                "CREATE TABLE app_meta (chave VARCHAR(100) PRIMARY KEY, valor VARCHAR(200))"
            ))
        _meta_set(conn, chave, valor)


def _migrar_hash_por_vencimento() -> None:
    """Recalcula hashes/duplicatas quando o critério de hash muda."""
    criterio_atual = "vencimento_documento"
    with engine.begin() as conn:
        if not _tabela_existe(conn, "movimentacoes"):
            return
        if not _tabela_existe(conn, "app_meta"):
            conn.execute(text(
                "CREATE TABLE app_meta (chave VARCHAR(100) PRIMARY KEY, valor VARCHAR(200))"
            ))
        if _meta_get(conn, "hash_criterio") == criterio_atual:
            return

    session = SessionLocal()
    try:
        from finance_app.services.hash_migration_service import recalcular_hashes_e_duplicatas
        recalcular_hashes_e_duplicatas(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    with engine.begin() as conn:
        _meta_set(conn, "hash_criterio", criterio_atual)


def _seed_bancos() -> None:
    from finance_app.database.repositories.banco_repo import BancoRepository

    session = SessionLocal()
    try:
        BancoRepository(session).seed_padrao()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """
    Inicializa o banco de dados, criando todas as tabelas,
    aplicando migrações leves e cadastrando os bancos padrão.
    """
    # É necessário importar os modelos antes de chamar create_all()
    from finance_app.database import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrar_schema()
    _seed_bancos()
    _migrar_hash_por_vencimento()


def reset_db() -> None:
    """
    Apaga todos os dados recriando o schema, sem deletar o arquivo SQLite.
    Evita WinError 32 no Windows quando o arquivo ainda está em uso.
    """
    from finance_app.database import models  # noqa: F401

    # Fecha sessões/conexões em pool e faz checkpoint do WAL
    with engine.begin() as conn:
        conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    engine.dispose()

    Base.metadata.drop_all(bind=engine)
    # Limpa metadados de migração de hash para forçar reseed limpo
    Base.metadata.create_all(bind=engine)
    _migrar_schema()
    _seed_bancos()
    with engine.begin() as conn:
        if _tabela_existe(conn, "app_meta"):
            _meta_set(conn, "hash_criterio", "vencimento_documento")
