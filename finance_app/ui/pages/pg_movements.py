"""
Página de Movimentações Detalhadas.
"""
import streamlit as st
import pandas as pd
from finance_app.database.connection import SessionLocal
from finance_app.ui.components.filters import render_global_filters
from finance_app.services import filter_service
from finance_app.database.models import Movimentacao
from finance_app.utils.dates import formatar_datas_dataframe

def renderizar_pagina():
    """Renderiza a página de movimentações detalhadas."""
    st.markdown("## 📊 Movimentações Detalhadas")
    st.markdown("Visualize e filtre todas as transações financeiras registradas no sistema.")
    st.divider()

    with SessionLocal() as session:
        # Renderizar filtros globais
        filtros = render_global_filters(session)

        # Filtro local específico desta página
        with st.expander("🔍 Busca Adicional", expanded=True):
            busca_titular = st.text_input(
                "Buscar Titular",
                placeholder="Digite o nome do titular (cliente/fornecedor)",
                help="Filtra os resultados pelo nome do titular associado à transação."
            )

        # Buscar dados
        query = filter_service.construir_query_movimentacoes(filtros)
        
        if busca_titular:
            query = query.filter(Movimentacao.titular.ilike(f"%{busca_titular}%"))

        # Executar query e converter para DataFrame
        df = pd.read_sql(query, session.bind)

        if df.empty:
            st.info("Nenhuma movimentação encontrada para os filtros selecionados.")
            return

        df = formatar_datas_dataframe(df)

        # Formatação e exibição
        st.markdown(f"**Total de Registros Encontrados:** {len(df):,}")
        
        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True
        )

if __name__ == "__main__":
    renderizar_pagina()
