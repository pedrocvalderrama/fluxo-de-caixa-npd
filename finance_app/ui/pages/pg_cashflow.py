"""
Página de Fluxo de Caixa Tabular Detalhado.
"""
import streamlit as st

from finance_app.database.connection import SessionLocal
from finance_app.ui.components.filters import render_global_filters
from finance_app.services.cashflow_service import (
    obter_fluxo_caixa_diario,
    obter_resumo_por_conta,
    obter_movimentacoes_simplificadas,
)
from finance_app.utils.dates import formatar_datas_dataframe
from finance_app.ui.components.tables import (
    render_resumo_empresa_banco,
    render_movimentacoes_simplificadas,
    render_fluxo_diario_tabela,
)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_fluxo_caixa(data_inicio, data_fim, empresas_ids, bancos_ids, grupos_categoria, status, ignorar_anomalias, ignorar_duplicatas, usar_saldo_manual=False, saldos_iniciais_por_conta=None, data_saldo_inicial=None):
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


def render_cashflow_page() -> None:
    """
    Renderiza a visão tabular do fluxo de caixa diário/mensal.
    """
    st.header("💸 Detalhamento do Fluxo de Caixa")

    with SessionLocal() as session:
        filtros = render_global_filters(session)

        empresas_tuple = tuple(filtros.empresas_ids) if filtros.empresas_ids else None
        bancos_tuple = tuple(filtros.bancos_ids) if filtros.bancos_ids else None
        grupos_tuple = tuple(filtros.grupos_categoria) if filtros.grupos_categoria else None
        saldos_tuple = tuple(sorted(filtros.saldos_iniciais_por_conta.items())) if filtros.saldos_iniciais_por_conta else None
        df_fluxo = _cached_fluxo_caixa(
            filtros.data_inicio, filtros.data_fim, empresas_tuple, bancos_tuple, grupos_tuple,
            filtros.status, filtros.ignorar_anomalias, filtros.ignorar_duplicatas,
            filtros.usar_saldo_manual, saldos_tuple, filtros.data_saldo_inicial
        )

        df_contas = obter_resumo_por_conta(session, filtros)
        if df_contas is not None and not df_contas.empty:
            render_resumo_empresa_banco(df_contas, titulo="🏦 Por Empresa e Banco")
            st.markdown("<br>", unsafe_allow_html=True)

        df_lancamentos = obter_movimentacoes_simplificadas(session, filtros)
        render_movimentacoes_simplificadas(df_lancamentos)
        st.markdown("<br>", unsafe_allow_html=True)

        if df_fluxo is None or df_fluxo.empty:
            st.info("Nenhum dado encontrado para o fluxo diário com os filtros selecionados.")
        else:
            render_fluxo_diario_tabela(
                df_fluxo, session=session, filtros=filtros, key="fluxo_diario_cashflow"
            )

            st.markdown("<br>", unsafe_allow_html=True)

            df_exibir = formatar_datas_dataframe(df_fluxo, colunas=["Data"])
            csv_data = df_exibir.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Exportar Dados (CSV)",
                data=csv_data,
                file_name="relatorio_fluxo_caixa.csv",
                mime="text/csv"
            )


if __name__ == "__main__":
    render_cashflow_page()
