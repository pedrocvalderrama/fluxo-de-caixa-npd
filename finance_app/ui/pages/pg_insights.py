"""
Página de Insights Automáticos e Anomalias.
"""
import streamlit as st
from finance_app.database.connection import SessionLocal
from finance_app.ui.components.filters import render_global_filters
from finance_app.services.insights_service import gerar_insights
from finance_app.services.anomaly_service import detectar_anomalias_transacoes
from finance_app.utils.dates import formatar_datas_dataframe


def render_insights_page() -> None:
    """
    Renderiza a página de Insights Automáticos e Anomalias.
    Apresenta dicas financeiras e um monitoramento de possíveis fraudes.
    """
    st.markdown("## 💡 Insights & Anomalias")
    st.markdown("Análise contínua automatizada e detecção estatística de despesas fora do padrão.")
    st.divider()

    with SessionLocal() as session:
        # Filtros globais
        filtros = render_global_filters(session)

        try:
            st.header("Feed de Insights")
            insights = gerar_insights(session, filtros)

            if insights:
                with st.container():
                    for insight in insights:
                        tipo = insight.get("tipo", "info")
                        msg = insight.get("mensagem", "")

                        if tipo == "positivo":
                            st.success(msg)
                        elif tipo == "negativo":
                            st.error(msg)
                        elif tipo == "alerta":
                            st.warning(msg)
                        else:
                            st.info(msg)
            else:
                st.info("Nenhum insight gerado para o período selecionado.")

            st.markdown("---")

            st.header("Monitoramento de Anomalias (Outliers)")

            anomalias_df = detectar_anomalias_transacoes(session, filtros)

            if anomalias_df is not None and not anomalias_df.empty:
                st.error(f"⚠️ Atenção! Foram detectadas {len(anomalias_df)} transação(ões) anômala(s) no período.")

                cols_to_show = ["data_transacao", "titular", "valor_absoluto", "motivo"]
                display_cols = [c for c in cols_to_show if c in anomalias_df.columns]

                if not display_cols:
                    display_cols = anomalias_df.columns

                st.dataframe(
                    formatar_datas_dataframe(anomalias_df[display_cols]),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success("Nenhuma transação anômala detectada no período.")

        except Exception as e:
            st.error(f"Erro ao carregar insights e anomalias: {e}")


if __name__ == "__main__":
    render_insights_page()
