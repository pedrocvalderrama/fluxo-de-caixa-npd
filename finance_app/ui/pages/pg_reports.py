"""
Página de Relatórios Gerenciais.
Permite configurar filtros e exportar dados consolidados em Excel ou CSV.
"""
import streamlit as st
import datetime
from finance_app.database.connection import SessionLocal
from finance_app.ui.components.filters import render_global_filters
from finance_app.services.export_service import exportar_para_excel, exportar_para_csv

def renderizar_pagina():
    """Renderiza a página de extração de relatórios."""
    st.markdown("## 📄 Relatórios Gerenciais")
    st.markdown("Exporte bases de dados customizadas para análise externa no Excel ou BI.")
    st.divider()

    with SessionLocal() as session:
        # Aproveita os filtros globais que já desenvolvemos
        st.markdown("### 1. Selecione os Parâmetros do Relatório")
        filtros = render_global_filters(session)
        
        st.divider()
        st.markdown("### 2. Exportação")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("Formato **Excel (.xlsx)**. Recomendado para relatórios prontos e formatações preservadas.")
            excel_bytes = exportar_para_excel(session, filtros)
            if excel_bytes:
                st.download_button(
                    label="📥 Baixar Excel",
                    data=excel_bytes,
                    file_name=f"relatorio_financeiro_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    type="primary"
                )
            else:
                st.warning("Não há dados para exportar com estes filtros.")
                
        with col2:
            st.info("Formato **CSV (.csv)**. Recomendado para importação em outros sistemas e planilhas grandes.")
            csv_bytes = exportar_para_csv(session, filtros)
            if csv_bytes:
                st.download_button(
                    label="📥 Baixar CSV",
                    data=csv_bytes,
                    file_name=f"relatorio_financeiro_{datetime.date.today().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning("Não há dados para exportar com estes filtros.")

if __name__ == "__main__":
    renderizar_pagina()
