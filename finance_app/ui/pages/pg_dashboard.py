"""
Página de Dashboard Principal.
"""
import streamlit as st

from finance_app.database.connection import SessionLocal
from finance_app.ui.components.filters import render_global_filters
from finance_app.services.dashboard_service import obter_kpis, obter_top_categorias
from finance_app.services.cashflow_service import (
    obter_fluxo_caixa_diario,
    calcular_saldo_inicial,
    obter_resumo_por_conta,
)
from finance_app.ui.components.metrics import render_kpi_cards
from finance_app.ui.components.charts import render_cashflow_chart, render_category_bar_chart
from finance_app.ui.components.tables import render_resumo_empresa_banco, render_fluxo_diario_tabela
@st.cache_data(ttl=300, show_spinner=False)
def _cached_kpis(data_inicio, data_fim, empresas_ids, bancos_ids, grupos_categoria, status, ignorar_anomalias, ignorar_duplicatas):
    """Cache de KPIs por 5 minutos."""
    from finance_app.database.connection import SessionLocal
    from finance_app.services.filter_service import FiltrosPesquisa
    filtros = FiltrosPesquisa(
        data_inicio=data_inicio, data_fim=data_fim,
        empresas_ids=tuple(empresas_ids) if empresas_ids else None,
        bancos_ids=tuple(bancos_ids) if bancos_ids else None,
        grupos_categoria=tuple(grupos_categoria) if grupos_categoria else None,
        status=status, ignorar_anomalias=ignorar_anomalias,
        ignorar_duplicatas=ignorar_duplicatas
    )
    with SessionLocal() as session:
        return obter_kpis(session, filtros)

@st.cache_data(ttl=300, show_spinner=False)
def _cached_fluxo(data_inicio, data_fim, empresas_ids, bancos_ids, grupos_categoria, status, ignorar_anomalias, ignorar_duplicatas, usar_saldo_manual=False, saldos_iniciais_por_conta=None, data_saldo_inicial=None):
    """Cache de fluxo de caixa por 5 minutos."""
    from finance_app.database.connection import SessionLocal
    from finance_app.services.filter_service import FiltrosPesquisa
    saldos_dict = dict(saldos_iniciais_por_conta) if saldos_iniciais_por_conta else {}
    filtros = FiltrosPesquisa(
        data_inicio=data_inicio, data_fim=data_fim,
        empresas_ids=tuple(empresas_ids) if empresas_ids else None,
        bancos_ids=tuple(bancos_ids) if bancos_ids else None,
        grupos_categoria=tuple(grupos_categoria) if grupos_categoria else None,
        status=status, ignorar_anomalias=ignorar_anomalias,
        ignorar_duplicatas=ignorar_duplicatas,
        usar_saldo_manual=usar_saldo_manual,
        saldos_iniciais_por_conta=saldos_dict,
        data_saldo_inicial=data_saldo_inicial
    )
    with SessionLocal() as session:
        return obter_fluxo_caixa_diario(session, filtros)


def render_dashboard() -> None:
    """
    Renderiza a visão executiva principal do sistema.
    """
    st.header("📊 Dashboard Executivo")

    # Inicia sessão de banco de dados
    with SessionLocal() as session:
        # Renderiza e obtém os filtros globais na interface
        filtros = render_global_filters(session)

        # Obtém os KPIs principais e o Fluxo de Caixa
        empresas_tuple = tuple(filtros.empresas_ids) if filtros.empresas_ids else None
        bancos_tuple = tuple(filtros.bancos_ids) if filtros.bancos_ids else None
        grupos_tuple = tuple(filtros.grupos_categoria) if filtros.grupos_categoria else None
        saldos_tuple = tuple(sorted(filtros.saldos_iniciais_por_conta.items())) if filtros.saldos_iniciais_por_conta else None

        kpis = _cached_kpis(
            filtros.data_inicio, filtros.data_fim, empresas_tuple, bancos_tuple, grupos_tuple,
            filtros.status, filtros.ignorar_anomalias, filtros.ignorar_duplicatas
        )
        df_fluxo = _cached_fluxo(
            filtros.data_inicio, filtros.data_fim, empresas_tuple, bancos_tuple, grupos_tuple,
            filtros.status, filtros.ignorar_anomalias, filtros.ignorar_duplicatas,
            filtros.usar_saldo_manual, saldos_tuple, filtros.data_saldo_inicial
        )

        # Calcula saldo inicial e final
        saldo_inicial = 0.0
        if filtros.data_inicio:
            saldo_inicial = calcular_saldo_inicial(
                session, 
                filtros.data_inicio, 
                filtros.empresas_ids,
                filtros.bancos_ids,
                usar_saldo_manual=filtros.usar_saldo_manual,
                saldos_iniciais_por_conta=filtros.saldos_iniciais_por_conta,
                data_saldo_inicial=filtros.data_saldo_inicial
            )
        elif df_fluxo is not None and not df_fluxo.empty:
            if "Saldo Inicial" in df_fluxo.columns:
                saldo_inicial = float(df_fluxo["Saldo Inicial"].iloc[0])
            else:
                saldo_inicial = float(
                    df_fluxo["Saldo Acumulado"].iloc[0] - df_fluxo["Resultado Diário"].iloc[0]
                )

        saldo_final = saldo_inicial + kpis.resultado

        # Renderiza KPIs
        render_kpi_cards(
            entradas=kpis.total_entradas,
            saidas=kpis.total_saidas,
            resultado=kpis.resultado,
            saldo_inicial=saldo_inicial,
            saldo_final=saldo_final,
        )

        st.markdown("---")

        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.subheader("📉 Fluxo de Caixa Diário")
            if df_fluxo is None or df_fluxo.empty:
                st.info("Nenhum dado encontrado para os filtros selecionados.")
            else:
                render_cashflow_chart(df_fluxo)

        with col_right:
            st.subheader("🏷️ Top Despesas por Categoria")
            try:
                top_cats = obter_top_categorias(session, filtros, limite=5)
                if top_cats:
                    render_category_bar_chart(top_cats)
                else:
                    st.info("Sem despesas no período.")
            except Exception:
                st.info("Sem despesas registradas no período.")

        st.markdown("---")
        render_fluxo_diario_tabela(
            df_fluxo, session=session, filtros=filtros, key="fluxo_diario_dashboard"
        )

        st.markdown("---")

        df_contas = obter_resumo_por_conta(session, filtros)
        if df_contas is not None and not df_contas.empty:
            render_resumo_empresa_banco(df_contas)


if __name__ == "__main__":
    render_dashboard()
