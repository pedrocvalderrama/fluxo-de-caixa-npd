"""
Página de Análise de Entradas (Receitas).
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from finance_app.database.connection import SessionLocal
from finance_app.ui.components.filters import render_global_filters
from finance_app.services import filter_service
from finance_app.utils.dates import formatar_datas_dataframe, PLOTLY_DATE_FORMAT


def renderizar_pagina():
    """Renderiza a página de Entradas (Receitas)."""
    st.markdown("## 📈 Análise de Entradas / Receitas")
    st.markdown("Visão focada na evolução do faturamento e principais clientes.")
    st.divider()

    with SessionLocal() as session:
        filtros = render_global_filters(session)
        # Forçar o tipo apenas para RECEBER
        filtros.tipos = ['RECEBER']

        query = filter_service.construir_query_movimentacoes(filtros)
        df = pd.read_sql(query, session.bind)

        if df.empty:
            st.info("Nenhuma entrada registrada para os filtros selecionados.")
            return

        if 'valor_absoluto' not in df.columns and 'valor' in df.columns:
            df['valor_absoluto'] = df['valor'].abs()

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### Evolução das Receitas ao Longo do Tempo")
            col_data = 'vencimento'
            if col_data in df.columns and df[col_data].notnull().any():
                df_temp = df.groupby(col_data)['valor_absoluto'].sum().reset_index()
                fig = px.line(
                    df_temp,
                    x=col_data,
                    y='valor_absoluto',
                    title="Receitas por Data",
                    labels={'valor_absoluto': 'Total (R$)', col_data: 'Data'},
                    template="plotly_dark"
                )
                fig.update_traces(line_color="#4ade80")
                fig.update_layout(
                    xaxis=dict(tickformat=PLOTLY_DATE_FORMAT, hoverformat=PLOTLY_DATE_FORMAT)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem dados de datas para exibir a evolução temporal.")

        with col2:
            st.markdown("### Top 10 Clientes / Titulares")
            if 'titular' in df.columns:
                top_clientes = df.groupby('titular')['valor_absoluto'].sum().nlargest(10).reset_index()
                fig_top = px.bar(
                    top_clientes,
                    x='valor_absoluto',
                    y='titular',
                    orientation='h',
                    title="Maiores Recebimentos",
                    labels={'valor_absoluto': 'Total (R$)', 'titular': 'Titular'},
                    template="plotly_dark"
                )
                fig_top.update_traces(marker_color="#4ade80")
                fig_top.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_top, use_container_width=True)

        st.markdown("---")
        st.markdown("### Tabela de Lançamentos de Entrada")
        st.dataframe(formatar_datas_dataframe(df), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    renderizar_pagina()
