import pytest
import pandas as pd
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finance_app.database.connection import Base
from finance_app.database.models import Empresa, Categoria, Importacao, Movimentacao, MovimentacaoRaw, Banco
from finance_app.config.bancos import BANCOS_PADRAO


@pytest.fixture
def engine_test():
    """Cria engine SQLite em memória com tabelas frescas para cada teste."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine_test):
    """Sessão isolada para cada teste com rollback automático."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def empresas_teste(session):
    """Cria 4 empresas de teste."""
    nomes = ["NPD", "COMPRE", "DEMO", "CS"]
    empresas = []
    for nome in nomes:
        emp = Empresa(codigo=nome, nome=nome)
        empresas.append(emp)
        session.add(emp)
    session.flush()
    for emp in empresas:
        session.refresh(emp)
    return empresas


@pytest.fixture
def bancos_teste(session):
    """Cria os 3 bancos padrão de teste."""
    bancos = []
    for codigo, nome in BANCOS_PADRAO:
        banco = Banco(codigo=codigo, nome=nome)
        bancos.append(banco)
        session.add(banco)
    session.flush()
    for banco in bancos:
        session.refresh(banco)
    return bancos


@pytest.fixture
def categorias_teste(session):
    """Cria 5 categorias de teste."""
    cats_data = [
        ("VDP", "VENDA DE PRODUTOS", "Vendas"),
        ("FR", "FR - FRETES VENDAS", "Fretes"),
        ("DF", "DF - TARIFAS BANCARIAS", "Desp. Financeiras"),
        ("IMP", "IMP - ICMS", "Impostos"),
        ("FUN", "FUN - SALARIOS SOS", "Funcionários"),
    ]
    categorias = []
    for codigo, nome, grupo in cats_data:
        cat = Categoria(codigo=codigo, nome=nome, grupo=grupo)
        categorias.append(cat)
        session.add(cat)
    session.flush()
    for cat in categorias:
        session.refresh(cat)
    return categorias


@pytest.fixture
def importacao_teste(session):
    """Cria uma importação de teste."""
    importacao = Importacao(
        arquivo="teste.xlsx",
        hash_arquivo="hash_test_123",
        qtd_registros=20,
        status="CONCLUIDA",
    )
    session.add(importacao)
    session.flush()
    session.refresh(importacao)
    return importacao


@pytest.fixture
def movimentacoes_teste(session, empresas_teste, bancos_teste, categorias_teste, importacao_teste):
    """Cria 20 movimentações de teste (10 PAGAR + 10 RECEBER)."""
    movs = []
    for i in range(20):
        tipo = "PAGAR" if i < 10 else "RECEBER"
        val = 100.0 * (i + 1)
        mov = Movimentacao(
            importacao_id=importacao_teste.id,
            empresa_id=empresas_teste[i % len(empresas_teste)].id,
            banco_id=bancos_teste[i % len(bancos_teste)].id,
            categoria_id=categorias_teste[i % len(categorias_teste)].id,
            data_transacao=date(2025, 1, (i % 28) + 1),
            vencimento=date(2025, 1, (i % 28) + 1),
            tipo=tipo,
            valor=-val if tipo == "PAGAR" else val,
            valor_absoluto=val,
            is_duplicata=False,
            is_anomalia_data=False,
            em_aberto=False,
        )
        movs.append(mov)
        session.add(mov)
    session.flush()
    for mov in movs:
        session.refresh(mov)
    return movs


@pytest.fixture
def df_excel_valido():
    data = {
        "empresa": ["NPD", "COMPRE"],
        "banco": ["Banco do Brasil", "Santander"],
        "movimentacao": ["PAGAR", "RECEBER"],
        "titular": ["Fornecedor A", "Cliente B"],
        "natureza": ["Material", "Venda"],
        "data_transacao": ["01/01/2025", "02/01/2025"],
        "vencimento": ["10/01/2025", "11/01/2025"],
        "valor": ["1500.00", "2000.00"],
        "linha_excel": [2, 3],
    }
    return pd.DataFrame(data)


@pytest.fixture
def df_excel_com_problemas():
    data = {
        "empresa": ["", "COMPRE"],
        "movimentacao": ["INVALIDO", "RECEBER"],
        "titular": ["Fornecedor A", "Cliente B"],
        "natureza": ["Material", "Venda"],
        "data_transacao": ["01/01/2025", "02/01/2025"],
        "vencimento": ["10/01/2025", "11/01/2025"],
        "valor": [None, "2000.00"],
        "linha_excel": [2, 3],
    }
    return pd.DataFrame(data)
