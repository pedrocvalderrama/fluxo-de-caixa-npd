import pytest
from datetime import date
from finance_app.services.dashboard_service import obter_kpis, obter_top_categorias
from finance_app.services.health_service import calcular_saude_financeira
from finance_app.services.insights_service import gerar_insights
from finance_app.services.filter_service import FiltrosPesquisa, construir_query_movimentacoes
from finance_app.database.models import Movimentacao, Importacao


def test_obter_kpis_basico(session, movimentacoes_teste):
    filtros = FiltrosPesquisa()
    kpis = obter_kpis(session, filtros)
    assert kpis.total_entradas > 0
    assert kpis.total_saidas < 0
    assert kpis.resultado == kpis.total_entradas + kpis.total_saidas


def test_obter_kpis_filtro_periodo(session, movimentacoes_teste):
    filtros = FiltrosPesquisa(data_inicio=date(2020, 1, 1), data_fim=date(2030, 1, 1))
    kpis = obter_kpis(session, filtros)
    assert kpis.total_entradas > 0 or kpis.total_saidas < 0


def test_obter_kpis_sem_dados(session, movimentacoes_teste):
    filtros = FiltrosPesquisa(data_inicio=date(2050, 1, 1), data_fim=date(2050, 12, 31))
    kpis = obter_kpis(session, filtros)
    assert kpis.total_entradas == 0.0
    assert kpis.total_saidas == 0.0


def test_obter_top_categorias(session, movimentacoes_teste):
    filtros = FiltrosPesquisa()
    top_cats = obter_top_categorias(session, filtros, limite=5)
    assert isinstance(top_cats, dict)


def test_saude_financeira_saudavel(session, movimentacoes_teste):
    filtros = FiltrosPesquisa()
    saude = calcular_saude_financeira(session, filtros)
    if saude.margem_operacional > 5:
        assert saude.score_geral in ['A', 'B']


def test_saude_financeira_critica(session, empresas_teste, categorias_teste, importacao_teste):
    """Cenário onde despesas superam receitas drasticamente."""
    mov = Movimentacao(
        importacao_id=importacao_teste.id,
        empresa_id=empresas_teste[0].id,
        categoria_id=categorias_teste[0].id,
        tipo='PAGAR',
        valor=-1000000.0,
        valor_absoluto=1000000.0,
        data_transacao=date(2024, 1, 1),
        vencimento=date(2024, 1, 1),
        is_duplicata=False,
        is_anomalia_data=False,
        em_aberto=False,
    )
    session.add(mov)
    session.flush()

    filtros = FiltrosPesquisa(data_inicio=date(2024, 1, 1), data_fim=date(2024, 1, 1))
    saude = calcular_saude_financeira(session, filtros)
    assert saude.score_geral in ['D', 'F']


def test_saude_pontos_fortes(session, movimentacoes_teste):
    filtros = FiltrosPesquisa()
    saude = calcular_saude_financeira(session, filtros)
    assert len(saude.pontos_fortes) > 0


def test_saude_pontos_atencao(session, movimentacoes_teste):
    filtros = FiltrosPesquisa()
    saude = calcular_saude_financeira(session, filtros)
    assert len(saude.pontos_atencao) > 0


def test_gerar_insights_basico(session, movimentacoes_teste):
    filtros = FiltrosPesquisa()
    insights = gerar_insights(session, filtros)
    assert isinstance(insights, list)
    assert len(insights) >= 2


def test_gerar_insights_tipo(session, movimentacoes_teste):
    filtros = FiltrosPesquisa()
    insights = gerar_insights(session, filtros)
    for insight in insights:
        assert 'tipo' in insight
        assert 'mensagem' in insight


def test_filtros_realizado(session, movimentacoes_teste):
    filtros = FiltrosPesquisa(status='realizado')
    q = construir_query_movimentacoes(filtros)
    str_q = str(q.compile(compile_kwargs={"literal_binds": True}))
    assert "data_transacao IS NOT NULL" in str_q


def test_filtros_projetado(session, movimentacoes_teste):
    filtros = FiltrosPesquisa(status='projetado')
    q = construir_query_movimentacoes(filtros)
    str_q = str(q.compile(compile_kwargs={"literal_binds": True}))
    assert "em_aberto" in str_q


def test_filtros_periodo_usa_vencimento(session, movimentacoes_teste):
    filtros = FiltrosPesquisa(
        status='realizado',
        data_inicio=date(2025, 1, 1),
        data_fim=date(2025, 1, 31),
    )
    q = construir_query_movimentacoes(filtros)
    str_q = str(q.compile(compile_kwargs={"literal_binds": True}))
    assert "vencimento" in str_q
    assert "2025-01-01" in str_q
    assert "2025-01-31" in str_q


def test_filtros_por_banco(session, movimentacoes_teste, bancos_teste):
    banco_id = bancos_teste[0].id
    filtros = FiltrosPesquisa(bancos_ids=[banco_id], status='todos')
    q = construir_query_movimentacoes(filtros)
    movs = session.scalars(q).all()
    assert movs
    assert all(m.banco_id == banco_id for m in movs)


def test_saldo_inicial_por_conta(session, empresas_teste, bancos_teste):
    from finance_app.services.cashflow_service import calcular_saldo_inicial

    emp_id = empresas_teste[0].id
    bb_id = next(b.id for b in bancos_teste if b.codigo == "001")
    sant_id = next(b.id for b in bancos_teste if b.codigo == "033")
    saldos = {
        (emp_id, bb_id): 1000.0,
        (emp_id, sant_id): 250.0,
    }
    total = calcular_saldo_inicial(
        session,
        date(2025, 1, 1),
        empresas_ids=[emp_id],
        bancos_ids=[bb_id],
        usar_saldo_manual=True,
        saldos_iniciais_por_conta=saldos,
        data_saldo_inicial=date(2025, 1, 1),
    )
    assert total == 1000.0


def test_resumo_por_conta(session, movimentacoes_teste, empresas_teste, bancos_teste):
    from finance_app.services.cashflow_service import obter_resumo_por_conta

    emp = empresas_teste[0]
    bb_id = next(b.id for b in bancos_teste if b.codigo == "001")
    sant_id = next(b.id for b in bancos_teste if b.codigo == "033")
    sic_id = next(b.id for b in bancos_teste if b.codigo == "748")

    filtros = FiltrosPesquisa(
        status='todos',
        usar_saldo_manual=True,
        saldos_iniciais_por_conta={
            (emp.id, bb_id): 100.0,
            (emp.id, sant_id): 200.0,
            (emp.id, sic_id): 300.0,
        },
        data_saldo_inicial=date(2025, 1, 1),
    )
    df = obter_resumo_por_conta(session, filtros)
    assert not df.empty
    assert set(df.columns) >= {"#", "Conta", "Saldo Inicial", "Entradas", "Saídas", "Resultado"}

    # Sempre lista os 3 bancos
    contas = df["Conta"].astype(str).str.strip()
    assert contas.str.contains("Banco do Brasil").any()
    assert contas.str.contains("Santander").any()
    assert contas.str.contains("Sicred").any()

    emp_row = df[df["Conta"].astype(str).str.strip() == emp.nome].iloc[0]
    assert abs(float(emp_row["Saldo Inicial"]) - 600.0) < 1e-6

    prefixo = str(emp_row["#"])
    bancos = df[df["#"].astype(str).str.match(rf"^{prefixo}\.\d+$")]
    assert abs(bancos["Saldo Inicial"].sum() - 600.0) < 1e-6
    assert abs(bancos["Resultado"].sum() - float(emp_row["Resultado"])) < 1e-6


def test_resumo_por_conta_sempre_tres_bancos(session, movimentacoes_teste, bancos_teste):
    from finance_app.services.cashflow_service import obter_resumo_por_conta

    # Movimentações de teste têm banco_id; mesmo assim a hierarquia usa os 3 oficiais
    filtros = FiltrosPesquisa(status='todos')
    df = obter_resumo_por_conta(session, filtros)
    # Pelo menos uma empresa com 3 linhas de banco
    emp = df[df["#"].astype(str).str.fullmatch(r"\d+")].iloc[0]["#"]
    bancos = df[df["#"].astype(str).str.match(rf"^{emp}\.\d+$")]
    nomes = bancos["Conta"].astype(str).str.strip().tolist()
    assert "Banco do Brasil" in nomes
    assert "Santander" in nomes
    assert "Sicred" in nomes


def test_construir_query_filtro_centro_custo(session, movimentacoes_teste):
    # Set centro_custo on one movement
    mov = movimentacoes_teste[0]
    mov.centro_custo = "INSUMOS"
    session.flush()

    filtros = FiltrosPesquisa(centros_custo=["INSUMOS"])
    query = construir_query_movimentacoes(filtros)
    resultados = session.execute(query).scalars().all()
    assert len(resultados) == 1
    assert resultados[0].centro_custo == "INSUMOS"

