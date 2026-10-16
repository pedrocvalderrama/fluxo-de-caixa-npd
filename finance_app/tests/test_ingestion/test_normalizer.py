import pytest
from datetime import date, datetime
import numpy as np
import pandas as pd
from types import SimpleNamespace
from finance_app.ingestion.normalizer import normalizar_linha, normalizar_dataframe, calcular_hash_registro

def create_row(**kwargs):
    default = {
        'linha_excel': 1, 'empresa': 'EMPRESA TESTE', 'movimentacao': 'PAGAR',
        'titular': 'FORNECEDOR A', 'natureza': 'FR - FRETES',
        'data_transacao': None, 'vencimento': None, 'valor': 1000.0
    }
    default.update(kwargs)
    return SimpleNamespace(**default)

def test_normalizar_linha_pagar():
    row = create_row(movimentacao='PAGAR', valor=1000)
    norm = normalizar_linha(row)
    assert norm.valor == -1000.0
    assert norm.valor_absoluto == 1000.0

def test_normalizar_linha_receber():
    row = create_row(movimentacao='RECEBER', valor=500)
    norm = normalizar_linha(row)
    assert norm.valor == 500.0
    assert norm.valor_absoluto == 500.0

def test_normalizar_linha_em_aberto():
    row = create_row(data_transacao=None)
    norm = normalizar_linha(row)
    assert norm.em_aberto is True

def test_normalizar_linha_com_data():
    row = create_row(data_transacao=datetime(2024, 6, 15))
    norm = normalizar_linha(row)
    assert norm.em_aberto is False
    assert norm.data_transacao == date(2024, 6, 15)

def test_normalizar_linha_data_anomala():
    row = create_row(vencimento=datetime(1899, 12, 29))
    norm = normalizar_linha(row)
    assert norm.is_anomalia_data is True

def test_normalizar_linha_natureza_com_espaco():
    row = create_row(natureza='FR - FRETES VENDAS ')
    norm = normalizar_linha(row)
    assert norm.natureza == 'FR - FRETES VENDAS'

def test_hash_determinismo():
    row = create_row()
    norm1 = normalizar_linha(row)
    norm2 = normalizar_linha(row)
    assert norm1.hash_registro == norm2.hash_registro

def test_hash_unicidade():
    row1 = create_row(valor=100)
    row2 = create_row(valor=200)
    norm1 = normalizar_linha(row1)
    norm2 = normalizar_linha(row2)
    assert norm1.hash_registro != norm2.hash_registro


def test_hash_usa_documento():
    row1 = create_row(documento='000007')
    row2 = create_row(documento='000008')
    norm1 = normalizar_linha(row1)
    norm2 = normalizar_linha(row2)
    assert norm1.documento == '000007'
    assert norm1.hash_registro != norm2.hash_registro


def test_hash_mesmo_documento_igual():
    row1 = create_row(documento='DUP-1')
    row2 = create_row(documento='DUP-1')
    assert normalizar_linha(row1).hash_registro == normalizar_linha(row2).hash_registro


def test_normalizar_dataframe_sucesso():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'A', 'movimentacao': 'PAGAR', 'titular': 'T', 'natureza': 'N', 'data_transacao': None, 'vencimento': None, 'valor': 10},
        {'linha_excel': 2, 'empresa': 'A', 'movimentacao': 'PAGAR', 'titular': 'T', 'natureza': 'N', 'data_transacao': None, 'vencimento': None, 'valor': 20},
        {'linha_excel': 3, 'empresa': 'A', 'movimentacao': 'PAGAR', 'titular': 'T', 'natureza': 'N', 'data_transacao': None, 'vencimento': None, 'valor': 30},
        {'linha_excel': 4, 'empresa': 'A', 'movimentacao': 'PAGAR', 'titular': 'T', 'natureza': 'N', 'data_transacao': None, 'vencimento': None, 'valor': 40},
        {'linha_excel': 5, 'empresa': 'A', 'movimentacao': 'PAGAR', 'titular': 'T', 'natureza': 'N', 'data_transacao': None, 'vencimento': None, 'valor': 50},
    ])
    norms, erros = normalizar_dataframe(df)
    assert len(norms) == 5
    assert len(erros) == 0

def test_normalizar_dataframe_com_erros():
    """Normalizar_dataframe deve capturar erros sem crashar."""
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'A', 'movimentacao': 'PAGAR', 'titular': 'T', 'natureza': 'N', 'data_transacao': None, 'vencimento': None, 'valor': 500},
    ])
    norms, erros = normalizar_dataframe(df)
    # O normalizer deve processar sem crashar, mesmo com dados mínimos
    assert len(norms) + len(erros) == 1

def test_prefixo_e_grupo():
    row = create_row(natureza='FR - FRETES')
    norm = normalizar_linha(row)
    assert norm.prefixo_categoria == 'FR'
    assert norm.grupo_categoria == 'Fretes'

def test_valor_nan_vira_zero():
    row = create_row(valor=np.nan)
    norm = normalizar_linha(row)
    assert norm.valor == 0.0


def test_normalizar_linha_banco_santander():
    row = create_row(banco='Santander')
    norm = normalizar_linha(row)
    assert norm.banco == '033'


def test_normalizar_linha_sem_banco():
    row = create_row()
    norm = normalizar_linha(row)
    assert norm.banco is None
