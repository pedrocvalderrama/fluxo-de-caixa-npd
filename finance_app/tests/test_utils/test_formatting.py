import pytest
from finance_app.utils.formatting import (
    normalizar_texto, extrair_prefixo_categoria, grupo_categoria,
    truncar_texto, formatar_numero, cor_variacao, icone_tendencia
)

def test_normalizar_texto():
    assert normalizar_texto("  hello   world  ") == "hello world"

def test_normalizar_texto_none():
    assert normalizar_texto(None) is None

def test_extrair_prefixo_fr():
    assert extrair_prefixo_categoria("FR - FRETES VENDAS") == ("FR", "FRETES VENDAS")

def test_extrair_prefixo_imp():
    assert extrair_prefixo_categoria("IMP - ICMS") == ("IMP", "ICMS")

def test_extrair_prefixo_sem_prefixo():
    assert extrair_prefixo_categoria("VENDA DE PRODUTOS") == (None, "VENDA DE PRODUTOS")

def test_extrair_prefixo_vazio():
    assert extrair_prefixo_categoria("") == (None, "")

def test_grupo_categoria_fr():
    assert grupo_categoria("FR") == "Fretes"

def test_grupo_categoria_imp():
    assert grupo_categoria("IMP") == "Impostos"

def test_grupo_categoria_none():
    assert grupo_categoria(None) == "Outros"

def test_grupo_categoria_desconhecido():
    assert grupo_categoria("XYZ") == "Outros"

def test_truncar_texto_curto():
    assert truncar_texto("abc", max_chars=50) == "abc"

def test_truncar_texto_longo():
    s = "a" * 100
    esperado = "a" * 47 + "..."
    assert truncar_texto(s, max_chars=50) == esperado

def test_truncar_texto_none():
    assert truncar_texto(None) == ""

def test_formatar_numero():
    assert formatar_numero(1234567.89, casas=2) == "1.234.567,89"

def test_cor_variacao():
    assert cor_variacao(10.0) == "green"
    assert cor_variacao(-5.0) == "red"
    assert cor_variacao(None) == "gray"

def test_icone_tendencia():
    assert icone_tendencia(10.0) == "📈"
    assert icone_tendencia(-5.0) == "📉"
    assert icone_tendencia(None) == "➡️"
