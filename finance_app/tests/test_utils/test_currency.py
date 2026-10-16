import pytest
import math
from finance_app.utils.currency import (
    formatar_moeda, formatar_moeda_resumida, parse_valor_br, parse_valor_excel,
    formatar_percentual, formatar_variacao, variacao_percentual
)

def test_formatar_moeda_positivo():
    assert formatar_moeda(1234.56) == "R$ 1.234,56"

def test_formatar_moeda_negativo():
    assert formatar_moeda(-500.0) == "R$ -500,00"

def test_formatar_moeda_zero():
    assert formatar_moeda(0) == "R$ 0,00"

def test_formatar_moeda_none():
    assert formatar_moeda(None) == "R$ 0,00"

def test_formatar_moeda_nan():
    assert formatar_moeda(float('nan')) == "R$ 0,00"

def test_formatar_moeda_sem_simbolo():
    assert formatar_moeda(100.0, com_simbolo=False) == "100,00"

def test_formatar_moeda_grande():
    assert formatar_moeda(1000000.50) == "R$ 1.000.000,50"

def test_formatar_moeda_resumida_mil():
    assert formatar_moeda_resumida(1500) == "R$ 1,5K"

def test_formatar_moeda_resumida_milhao():
    assert formatar_moeda_resumida(1500000) == "R$ 1,5M"

def test_formatar_moeda_resumida_bilhao():
    assert formatar_moeda_resumida(2000000000) == "R$ 2,0B"

def test_parse_valor_br():
    assert parse_valor_br("1.234,56") == 1234.56

def test_parse_valor_br_com_rs():
    assert parse_valor_br("R$ 1.234,56") == 1234.56

def test_parse_valor_br_vazio():
    assert parse_valor_br("") is None

def test_parse_valor_br_none():
    assert parse_valor_br(None) is None

def test_parse_valor_excel_int():
    assert parse_valor_excel(100) == 100.0

def test_parse_valor_excel_float():
    assert parse_valor_excel(100.5) == 100.5

def test_parse_valor_excel_nan():
    assert parse_valor_excel(float('nan')) is None

def test_parse_valor_excel_none():
    assert parse_valor_excel(None) is None

def test_variacao_percentual():
    assert variacao_percentual(120, 100) == 20.0

def test_variacao_percentual_negativa():
    assert variacao_percentual(80, 100) == -20.0

def test_variacao_percentual_zero_anterior():
    assert variacao_percentual(100, 0) is None

def test_formatar_percentual():
    assert formatar_percentual(15.5) == "15,5%"

def test_formatar_variacao_positiva():
    assert formatar_variacao(10.0) == ("+10,0%", "green")

def test_formatar_variacao_negativa():
    assert formatar_variacao(-10.0) == ("-10,0%", "red")
