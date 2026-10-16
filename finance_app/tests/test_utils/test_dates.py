import pytest
import pandas as pd
from datetime import date, datetime, timedelta
from finance_app.utils.dates import (
    parse_data_excel, is_data_anomala, formatar_data,
    periodos_rapidos, dias_uteis_no_periodo,
    primeiro_dia_mes, ultimo_dia_mes, mes_anterior
)

def test_parse_data_excel_datetime():
    assert parse_data_excel(datetime(2024, 12, 25)) == date(2024, 12, 25)

def test_parse_data_excel_string_br():
    assert parse_data_excel("25/12/2024") == date(2024, 12, 25)

def test_parse_data_excel_none():
    assert parse_data_excel(None) is None

def test_parse_data_excel_nat():
    assert parse_data_excel(pd.NaT) is None

def test_parse_data_excel_serial():
    expected = (datetime(1899, 12, 30) + timedelta(days=45292)).date()
    assert parse_data_excel(45292) == expected

def test_is_data_anomala_normal():
    assert is_data_anomala(date(2024, 6, 15)) is False

def test_is_data_anomala_antiga():
    assert is_data_anomala(date(1899, 12, 29)) is True

def test_is_data_anomala_futura():
    assert is_data_anomala(date(2054, 2, 25)) is True

def test_is_data_anomala_none():
    assert is_data_anomala(None) is False

def test_formatar_data():
    assert formatar_data(date(2024, 3, 15)) == "15/03/2024"

def test_formatar_data_none():
    assert formatar_data(None) == ""

def test_formatar_datas_dataframe():
    from finance_app.utils.dates import formatar_datas_dataframe
    df = pd.DataFrame({
        "Data": [date(2026, 1, 30), date(2026, 8, 13)],
        "Valor": [10.0, 20.0],
    })
    out = formatar_datas_dataframe(df, colunas=["Data"])
    assert list(out["Data"]) == ["30/01/2026", "13/08/2026"]
    assert list(out["Valor"]) == [10.0, 20.0]

def test_periodos_rapidos():
    periodos = periodos_rapidos()
    assert len(periodos) == 8
    for chave, valor in periodos.items():
        assert isinstance(chave, str)
        assert isinstance(valor, tuple)
        assert len(valor) == 2
        assert isinstance(valor[0], date)
        assert isinstance(valor[1], date)

def test_dias_uteis():
    inicio = date(2024, 1, 1) # Seg
    fim = date(2024, 1, 7) # Dom
    assert dias_uteis_no_periodo(inicio, fim) == 5

def test_primeiro_ultimo_dia_mes():
    d = date(2024, 2, 15)
    assert primeiro_dia_mes(d) == date(2024, 2, 1)
    assert ultimo_dia_mes(d) == date(2024, 2, 29)

def test_mes_anterior():
    d = date(2024, 3, 15)
    inicio, fim = mes_anterior(d)
    assert inicio == date(2024, 2, 1)
    assert fim == date(2024, 2, 29)
