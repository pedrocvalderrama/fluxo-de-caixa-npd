from finance_app.config.bancos import resolver_codigo_banco, BANCOS_PADRAO


def test_bancos_padrao_sao_tres():
    assert len(BANCOS_PADRAO) == 3
    nomes = [nome for _, nome in BANCOS_PADRAO]
    assert nomes == ["Banco do Brasil", "Santander", "Sicred"]


def test_resolver_banco_do_brasil():
    assert resolver_codigo_banco("Banco do Brasil") == "001"
    assert resolver_codigo_banco("001") == "001"
    assert resolver_codigo_banco("BB") == "001"


def test_resolver_santander():
    assert resolver_codigo_banco("Santander") == "033"
    assert resolver_codigo_banco("033") == "033"


def test_resolver_sicred():
    assert resolver_codigo_banco("Sicred") == "748"
    assert resolver_codigo_banco("Sicredi") == "748"
    assert resolver_codigo_banco("748") == "748"


def test_resolver_banco_vazio_ou_desconhecido():
    assert resolver_codigo_banco(None) is None
    assert resolver_codigo_banco("") is None
    assert resolver_codigo_banco("Nubank") is None
