"""
Página de Análise por Categorias.

Fornece uma visão hierárquica (Treemap) e tabular das receitas e despesas
distribuídas por grupos e categorias.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from finance_app.database.connection import SessionLocal
from finance_app.ui.components.filters import render_global_filters
from finance_app.services import category_service
@st.cache_data(ttl=300, show_spinner=False)
def _cached_categorias(data_inicio, data_fim, empresas_ids, bancos_ids, grupos_categoria, status, ignorar_anomalias, ignorar_duplicatas, tipo_movimento):
    """Cache de categorias por 5 minutos."""
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
        from finance_app.services import category_service
        return category_service.obter_analise_categorias(session, filtros, tipo_movimento=tipo_movimento)

def renderizar_pagina():
    """Renderiza a página de análise por categoria."""
    st.markdown("## 🗂️ Análise por Categorias")
    st.markdown("Entenda para onde vai ou de onde vem o dinheiro através de uma visão estruturada.")
    st.divider()

    with SessionLocal() as session:
        # Filtros Globais
        filtros = render_global_filters(session)

        # Toggle UI
        analise_tipo = st.radio(
            "Selecione o tipo de análise:",
            options=["Analisar Despesas", "Analisar Receitas"],
            horizontal=True
        )
        
        tipo_movimento = 'PAGAR' if analise_tipo == "Analisar Despesas" else 'RECEBER'

        # Obter Análise do Serviço
        empresas_tuple = tuple(filtros.empresas_ids) if filtros.empresas_ids else None
        bancos_tuple = tuple(filtros.bancos_ids) if filtros.bancos_ids else None
        grupos_tuple = tuple(filtros.grupos_categoria) if filtros.grupos_categoria else None
        df_categorias = _cached_categorias(
            filtros.data_inicio, filtros.data_fim, empresas_tuple, bancos_tuple, grupos_tuple,
            filtros.status, filtros.ignorar_anomalias, filtros.ignorar_duplicatas,
            tipo_movimento
        )

        if df_categorias is None or df_categorias.empty:
            st.info("Nenhuma categoria encontrada para os parâmetros definidos.")
            return

        st.markdown("### 🗺️ Mapa de Categorias")
        
        try:
            fig_treemap = px.treemap(
                df_categorias,
                path=[px.Constant("Todas as Categorias"), 'Grupo', 'Categoria'],
                values='Valor Absoluto',
                color='Valor Absoluto',
                color_continuous_scale="Reds" if tipo_movimento == 'PAGAR' else "Greens",
                template="plotly_dark"
            )
            fig_treemap.update_traces(root_color="lightgrey")
            fig_treemap.update_layout(margin=dict(t=30, l=10, r=10, b=10))
            st.plotly_chart(fig_treemap, use_container_width=True)
        except Exception as e:
            st.error(f"Não foi possível renderizar o treemap: {e}")

        st.markdown("### 📋 Tabela Detalhada")
        
        st.dataframe(
            df_categorias,
            column_config={
                "Grupo": st.column_config.TextColumn("Grupo"),
                "Categoria": st.column_config.TextColumn("Categoria"),
                "Valor Absoluto": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                "% Representação": st.column_config.NumberColumn("Representação (%)", format="%.2f%%"),
            },
            hide_index=True,
            use_container_width=True
        )

if __name__ == "__main__":
    renderizar_pagina()
