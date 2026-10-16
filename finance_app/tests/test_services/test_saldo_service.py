"""
Testes unitários e de integração para o serviço de atualização de saldo diário (saldo_service.py).
"""
import pytest
from datetime import date, datetime
import tempfile
import openpyxl

from finance_app.services.saldo_service import (
    _parse_valor,
    _parse_data,
    ler_e_atualizar_saldo_excel,
    obter_saldo_mais_recente,
    obter_historico_saldos,
    salvar_saldos_banco,
    obter_saldo_por_data,
    listar_datas_com_saldo,
    backfill_saldos_consolidados,
    MAPEAMENTO_SALDO_EXCEL,
    DEFAULT_SALDO_EXCEL_PATH,
)
from finance_app.database.connection import get_session, init_db
from finance_app.database.models import SaldoDiario, SaldoDiarioConsolidado, Empresa, Banco


def test_parse_valor():
    assert _parse_valor(None) == 0.0
    assert _parse_valor(1500) == 1500.0
    assert _parse_valor(1234.56) == 1234.56
    assert _parse_valor("206.711,45") == 206711.45
    assert _parse_valor("R$ 63.078,90") == 63078.90
    assert _parse_valor("R$  7.668,68 ") == 7668.68
    assert _parse_valor("100,50") == 100.50
    assert _parse_valor("100.50") == 100.50
    assert _parse_valor("") == 0.0


def test_parse_data():
    assert _parse_data(date(2026, 9, 16)) == date(2026, 9, 16)
    assert _parse_data(datetime(2026, 9, 16, 12, 0)) == date(2026, 9, 16)
    assert _parse_data("16/09/2026") == date(2026, 9, 16)
    assert _parse_data("2026-09-16") == date(2026, 9, 16)
    assert _parse_data("16/9/26") == date(2026, 9, 16)
    assert _parse_data("invalido") is None


def test_ler_e_atualizar_saldo_excel_mock(session, empresas_teste, bancos_teste):
    # Cria uma planilha temporária com a mesma estrutura
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Planilha1"

    # Linha 1 Col C -> Data
    ws.cell(1, 3, "16/09/2026")

    # Linha 3 -> CS BB
    ws.cell(3, 3, 206711.45)
    # Linha 4 -> CS Sicredi
    ws.cell(4, 3, 63078.90)
    # Linha 6 -> NPD BB
    ws.cell(6, 3, 7668.68)
    # Linha 7 -> NPD Santander
    ws.cell(7, 3, 6311.69)
    # Linha 8 -> NPD Sicredi
    ws.cell(8, 3, 7988.13)
    # Linha 10 -> COMPRE BB
    ws.cell(10, 3, 91575.45)
    # Linha 11 -> COMPRE Santander
    ws.cell(11, 3, 23974.39)
    # Linha 12 -> COMPRE Sicredi
    ws.cell(12, 3, 17331.31)

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name
        wb.save(tmp_path)

    try:
        res = ler_e_atualizar_saldo_excel(tmp_path, session=session)
        assert res["sucesso"] is True
        assert res["data"] == date(2026, 9, 16)
        assert round(res["total_geral"], 2) == 424640.00
        assert len(res["detalhes"]) == 8

        # Verifica se está gravado no banco para a data do teste
        registros = session.query(SaldoDiario).filter(SaldoDiario.data == date(2026, 9, 16)).all()
        assert len(registros) == 8
        assert round(sum(r.saldo for r in registros), 2) == 424640.00

        # Testa idempotência / upsert (executa novamente sem duplicar)
        res2 = ler_e_atualizar_saldo_excel(tmp_path, session=session)
        assert res2["sucesso"] is True
        count = session.query(SaldoDiario).filter(SaldoDiario.data == date(2026, 9, 16)).count()
        assert count == 8
    finally:
        import os
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def test_calcular_saldo_inicial_usa_saldo_diario_automaticamente(session, empresas_teste, bancos_teste):
    from finance_app.services.cashflow_service import calcular_saldo_inicial

    # Insere registros de SaldoDiario na sessão isolada
    emp_npd = next(e for e in empresas_teste if "NPD" in e.nome)
    bco_bb = next(b for b in bancos_teste if "Brasil" in b.nome)
    session.add(SaldoDiario(data=date(2026, 9, 16), empresa_id=emp_npd.id, banco_id=bco_bb.id, saldo=424640.00))
    session.commit()

    # Quando usar_saldo_manual=False, deve buscar automaticamente os registros de SaldoDiario
    saldo = calcular_saldo_inicial(
        session=session,
        data_inicio=date(2026, 9, 16),
        usar_saldo_manual=False,
        saldos_iniciais_por_conta=None,
        data_saldo_inicial=None,
    )
    assert round(saldo, 2) == 424640.00


def test_salvar_saldos_banco_e_obter(session, empresas_teste, bancos_teste):
    emp_npd = next(e for e in empresas_teste if "NPD" in e.nome)
    emp_compre = next((e for e in empresas_teste if "COMPRE" in e.nome), None)
    bco_bb = bancos_teste[0]

    assert emp_npd is not None
    assert bco_bb is not None

    dt_teste = date(2026, 12, 1)
    saldos_map = {
        (emp_npd.id, bco_bb.id): 50000.0,
    }
    if emp_compre:
        saldos_map[(emp_compre.id, bco_bb.id)] = 25000.0

    res = salvar_saldos_banco(dt_teste, saldos_map, origem="MANUAL", session=session)
    assert res["sucesso"] is True
    esperado_total = 75000.0 if emp_compre else 50000.0
    assert res["total_geral"] == esperado_total
    assert res["saldo_npd"] == 50000.0

    # Verifica obter_saldo_por_data
    rec = obter_saldo_por_data(dt_teste, session=session)
    assert rec is not None
    assert rec["total_geral"] == esperado_total
    assert rec["saldos"][(emp_npd.id, bco_bb.id)] == 50000.0
    assert rec["origem"] == "MANUAL"

    # Verifica listar_datas_com_saldo
    lista = listar_datas_com_saldo(session)
    datas = [d["data"] for d in lista]
    assert dt_teste in datas

    # Verifica se SaldoDiarioConsolidado tem o registro
    cons = session.query(SaldoDiarioConsolidado).filter(SaldoDiarioConsolidado.data == dt_teste).first()
    assert cons is not None
    assert cons.saldo_total == esperado_total
    assert cons.saldo_npd == 50000.0
