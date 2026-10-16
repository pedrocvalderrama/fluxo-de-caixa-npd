"""
Página de Saúde Financeira.
"""
import streamlit as st
from finance_app.database.connection import SessionLocal
from finance_app.ui.components.filters import render_global_filters
from finance_app.services.health_service import calcular_saude_financeira


def render_health_page() -> None:
    """
    Renderiza a página de Saúde Financeira.
    Exibe o score de saúde, indicadores e pontos de análise.
    """
    st.markdown("## ❤️ Saúde Financeira")
    st.markdown("Avaliação algorítmica da liquidez e eficiência operacional da sua empresa.")
    st.divider()

    with SessionLocal() as session:
        # Filtros globais
        filtros = render_global_filters(session)

        try:
            saude = calcular_saude_financeira(session, filtros)

            if not saude:
                st.info("Dados insuficientes para calcular a saúde financeira no período selecionado.")
                return

            score_geral = getattr(saude, "score_geral", "N/A")
            margem = getattr(saude, "margem_operacional", 0.0)
            liquidez = getattr(saude, "indice_liquidez", 0.0)
            fortes = getattr(saude, "pontos_fortes", [])
            atencao = getattr(saude, "pontos_atencao", [])

            # Definir a cor baseada no score para um design premium em tema escuro
            color = "#888888"  # Cinza neutro por padrão
            if score_geral in ["A", "B"]:
                color = "#4CAF50"  # Verde
            elif score_geral == "C":
                color = "#FFC107"  # Amarelo
            elif score_geral in ["D", "F"]:
                color = "#F44336"  # Vermelho

            st.markdown(
                f"""
            <div style="text-align: center; padding: 2rem; background-color: #1E1E1E; border-radius: 12px; margin-bottom: 2rem; box-shadow: 0 4px 8px rgba(0,0,0,0.5); border: 1px solid #333;">
                <h3 style="color: #E0E0E0; font-weight: 400; margin-bottom: 10px;">Score Geral de Saúde</h3>
                <h1 style="color: {color}; font-size: 5rem; font-weight: 800; margin: 0; line-height: 1;">{score_geral}</h1>
            </div>
            """,
                unsafe_allow_html=True,
            )

            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="Margem Operacional (%)", value=f"{margem:.2f}%")
            with col2:
                st.metric(label="Índice de Liquidez (Entradas/Saídas)", value=f"{liquidez:.2f}")

            st.markdown("---")

            col_fortes, col_atencao = st.columns(2)

            with col_fortes:
                st.subheader("💪 Pontos Fortes")
                if fortes:
                    for ponto in fortes:
                        st.success(ponto)
                else:
                    st.write("Sem pontos fortes identificados no momento.")

            with col_atencao:
                st.subheader("⚠️ Pontos de Atenção")
                if atencao:
                    for ponto in atencao:
                        st.warning(ponto)
                else:
                    st.write("Sem pontos de atenção críticos no momento.")

        except Exception as e:
            st.error(f"Erro ao calcular a saúde financeira: {e}")


if __name__ == "__main__":
    render_health_page()
