import pytest
import pandas as pd
from datetime import datetime
from finance_app.ingestion.validator import validar_dataframe, SeveridadeProblema

def test_validar_tudo_valido():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'EMP1', 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': 100},
        {'linha_excel': 2, 'empresa': 'EMP1', 'movimentacao': 'RECEBER', 'titular': 'T2', 'natureza': 'N2', 'data_transacao': datetime(2024,1,2), 'vencimento': None, 'valor': 200},
        {'linha_excel': 3, 'empresa': 'EMP1', 'movimentacao': 'PAGAR', 'titular': 'T3', 'natureza': 'N3', 'data_transacao': datetime(2024,1,3), 'vencimento': None, 'valor': 300},
    ])
    res = validar_dataframe(df)
    assert res.linhas_validas == 3
    assert res.pode_importar is True

def test_validar_banco_desconhecido():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'EMP1', 'banco': 'Nubank', 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': 100},
    ])
    res = validar_dataframe(df)
    assert any(p.coluna == 'banco' and p.severidade == SeveridadeProblema.AVISO for p in res.problemas)

def test_validar_empresa_vazia():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': '', 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': 100},
    ])
    res = validar_dataframe(df)
    assert res.linhas_com_erro == 1
    assert any(p.severidade == SeveridadeProblema.ERRO and p.coluna == 'empresa' for p in res.problemas)

def test_validar_empresa_none():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': None, 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': 100},
    ])
    res = validar_dataframe(df)
    assert res.linhas_com_erro == 1

def test_validar_movimentacao_invalida():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'EMP1', 'movimentacao': 'TRANSFERIR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': 100},
    ])
    res = validar_dataframe(df)
    assert res.linhas_com_erro == 1
    assert any(p.coluna == 'movimentacao' for p in res.problemas)

def test_validar_valor_vazio():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'EMP1', 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': ''},
    ])
    res = validar_dataframe(df)
    assert res.linhas_com_erro == 1

def test_validar_valor_nao_numerico():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'EMP1', 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': 'abc'},
    ])
    res = validar_dataframe(df)
    assert res.linhas_com_erro == 1

def test_validar_valor_negativo():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'EMP1', 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': -100},
    ])
    res = validar_dataframe(df)
    assert res.linhas_com_aviso == 1
    assert any(p.severidade == SeveridadeProblema.AVISO and p.coluna == 'valor' for p in res.problemas)

def test_validar_valor_zero():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'EMP1', 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': 0},
    ])
    res = validar_dataframe(df)
    assert res.linhas_com_valor_zero == 1

def test_validar_data_anomala():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'EMP1', 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(1899,1,1), 'vencimento': None, 'valor': 100},
    ])
    res = validar_dataframe(df)
    assert any(p.severidade == SeveridadeProblema.AVISO and p.coluna == 'data_transacao' for p in res.problemas)

def test_validar_titular_vazio():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'EMP1', 'movimentacao': 'PAGAR', 'titular': '', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': 100},
    ])
    res = validar_dataframe(df)
    assert res.linhas_com_aviso == 1
    assert any(p.coluna == 'titular' for p in res.problemas)

def test_validar_natureza_vazia():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'EMP1', 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': '', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': 100},
    ])
    res = validar_dataframe(df)
    assert res.linhas_com_aviso == 1
    assert any(p.coluna == 'natureza' for p in res.problemas)

def test_validar_em_aberto():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'EMP1', 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': None, 'vencimento': None, 'valor': 100},
    ])
    res = validar_dataframe(df)
    assert res.linhas_em_aberto == 1
    assert any(p.severidade == SeveridadeProblema.INFO for p in res.problemas)

def test_pode_importar_false():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': '', 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': 100},
        {'linha_excel': 2, 'empresa': 'EMP1', 'movimentacao': 'TRANSFERIR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': 100},
    ])
    res = validar_dataframe(df)
    assert res.pode_importar is False

def test_resumo_texto():
    df = pd.DataFrame([
        {'linha_excel': 1, 'empresa': 'EMP1', 'movimentacao': 'PAGAR', 'titular': 'T1', 'natureza': 'N1', 'data_transacao': datetime(2024,1,1), 'vencimento': None, 'valor': 100},
    ])
    res = validar_dataframe(df)
    txt = res.resumo_texto()
    assert "Total de registros: 1" in txt
    assert "Registros válidos: 1" in txt
