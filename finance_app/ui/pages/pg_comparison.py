"""
Página de Comparação de Cenários.

Permite analisar os resultados de dois períodos distintos lado a lado,
destacando variações percentuais.
"""

import streamlit as st
import datetime
from copy import deepcopy
from finance_app.database.connection import SessionLocal
from finance_app.ui.components.filters import render_global_filters
from finance_app.services import comparison_service
from finance_app.utils.dates import STREAMLIT_DATE_FORMAT

def renderizar_pagina():
    """Renderiza a página de comparação de cenários."""
    st.markdown("## ⚖️ Comparação de Cenários")
    st.markdown("Compare indicadores financeiros entre dois períodos distintos.")
    st.divider()

    with SessionLocal() as session:
        # Pega as demais seleções como empresas/categorias do global
        filtros_globais = render_global_filters(session)

        st.markdown("### 📅 Definição de Períodos")
        colA, colB = st.columns(2)
        
        with colA:
            st.markdown("**Cenário A (Referência)**")
            data_inicio_a = st.date_input(
                "Início Período A", datetime.date.today().replace(day=1),
                key="dt_in_a", format=STREAMLIT_DATE_FORMAT,
            )
            data_fim_a = st.date_input(
                "Fim Período A", datetime.date.today(),
                key="dt_fim_a", format=STREAMLIT_DATE_FORMAT,
            )
            
        with colB:
            st.markdown("**Cenário B (Comparação)**")
            # Default para mês anterior
            mes_anterior = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
            inicio_mes_anterior = mes_anterior.replace(day=1)
            
            data_inicio_b = st.date_input(
                "Início Período B", inicio_mes_anterior,
                key="dt_in_b", format=STREAMLIT_DATE_FORMAT,
            )
            data_fim_b = st.date_input(
                "Fim Período B", mes_anterior,
                key="dt_fim_b", format=STREAMLIT_DATE_FORMAT,
            )

        if st.button("🔄 Comparar Cenários", use_container_width=True):
            # Criação dos filtros isolados baseados no global
            filtros_A = deepcopy(filtros_globais)
            filtros_A.data_inicio = data_inicio_a
            filtros_A.data_fim = data_fim_a
            
            filtros_B = deepcopy(filtros_globais)
            filtros_B.data_inicio = data_inicio_b
            filtros_B.data_fim = data_fim_b

            # Obter dados
            resultado = comparison_service.comparar_periodos(session, filtros_A, filtros_B)

            st.markdown("### 📊 Resultados da Comparação")
            st.caption("A variação indica o quanto o Cenário A representa em relação ao Cenário B.")
            
            col_rec, col_desp, col_res = st.columns(3)
            
            with col_rec:
                rec_val = resultado.get('receitas', {}).get('A', 0.0)
                rec_var = resultado.get('receitas', {}).get('var_pct')
                delta_rec = f"{rec_var:.2f}%" if rec_var is not None else None
                st.metric(
                    "Receitas (Cenário A)", 
                    f"R$ {rec_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    delta=delta_rec
                )
                
            with col_desp:
                desp_val = resultado.get('despesas', {}).get('A', 0.0)
                desp_var = resultado.get('despesas', {}).get('var_pct')
                delta_desp = f"{desp_var:.2f}%" if desp_var is not None else None
                st.metric(
                    "Despesas (Cenário A)", 
                    f"R$ {desp_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    delta=delta_desp,
                    delta_color="inverse"
                )
                
            with col_res:
                res_val = resultado.get('resultado', {}).get('A', 0.0)
                res_var = resultado.get('resultado', {}).get('var_pct')
                delta_res = f"{res_var:.2f}%" if res_var is not None else None
                st.metric(
                    "Resultado Líquido (Cenário A)", 
                    f"R$ {res_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    delta=delta_res
                )

if __name__ == "__main__":
    renderizar_pagina()
