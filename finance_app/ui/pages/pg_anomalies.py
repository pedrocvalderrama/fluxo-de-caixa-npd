"""
Página de Anomalias e Duplicatas.
Lista tudo que foi marcado na importação como data anômala ou duplicata.
"""
import streamlit as st

from finance_app.database.connection import SessionLocal
from finance_app.ui.components.filters import render_global_filters
from finance_app.services.anomaly_duplicate_service import obter_anomalias, obter_duplicatas


def _render_tabela_anomalias(df) -> None:
    st.subheader("🔴 Anomalias de Data")
    st.caption("Critério: vencimento ou data da transação antes de 1950 ou após 2050.")
    if df is None or df.empty:
        st.success("Nenhuma anomalia de data encontrada para os filtros selecionados.")
        return

    st.caption(f"Total: {len(df):,}".replace(",", "."))
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=min(560, (min(len(df), 14) + 1) * 37 + 8),
        column_config={
            "Empresa": st.column_config.TextColumn("Empresa"),
            "Banco": st.column_config.TextColumn("Banco"),
            "vencimento": st.column_config.TextColumn("Vencimento"),
            "data_transacao": st.column_config.TextColumn("Data Transação"),
            "titular": st.column_config.TextColumn("Titular"),
            "tipo": st.column_config.TextColumn("Tipo"),
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
            "motivo": st.column_config.TextColumn("Motivo"),
        },
    )


def _render_tabela_duplicatas(df) -> None:
    st.subheader("🟡 Duplicatas")
    st.caption(
        "Critério: lançamentos com o **mesmo hash** "
        "(empresa + banco + tipo + titular + natureza + vencimento + valor). "
        "Se qualquer ocorrência cair no período filtrado, a tabela traz **todas** as "
        "ocorrências do grupo (mesmo com vencimento fora do filtro)."
    )
    if df is None or df.empty:
        st.success("Nenhuma duplicata encontrada para os filtros selecionados.")
        return

    n_grupos = int(df["Grupo"].nunique()) if "Grupo" in df.columns else 0
    st.caption(
        f"Total de lançamentos: {len(df):,} em {n_grupos:,} grupos".replace(",", ".")
    )
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=min(560, (min(len(df), 14) + 1) * 37 + 8),
        column_config={
            "Grupo": st.column_config.NumberColumn("Grupo", format="%d"),
            "Ocorrência": st.column_config.TextColumn("Ocorrência"),
            "Empresa": st.column_config.TextColumn("Empresa"),
            "Banco": st.column_config.TextColumn("Banco"),
            "vencimento": st.column_config.TextColumn("Vencimento"),
            "data_transacao": st.column_config.TextColumn("Data Transação"),
            "titular": st.column_config.TextColumn("Titular"),
            "natureza": st.column_config.TextColumn("Natureza"),
            "tipo": st.column_config.TextColumn("Tipo"),
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
            "marcado_duplicata": st.column_config.TextColumn("Marcado na importação"),
            "motivo": st.column_config.TextColumn("Motivo"),
        },
    )


def render_anomalies_page() -> None:
    """Renderiza a página de anomalias e duplicatas."""
    st.header("⚠️ Anomalias / Duplicatas")
    st.markdown(
        "Registros sinalizados na importação: datas fora do intervalo esperado "
        "e lançamentos idênticos (mesmo hash por vencimento)."
    )
    st.divider()

    with SessionLocal() as session:
        filtros = render_global_filters(session)
        filtros.ignorar_anomalias = False
        filtros.ignorar_duplicatas = False

        df_anomalias = obter_anomalias(session, filtros)
        df_duplicatas = obter_duplicatas(session, filtros)

        n_grupos = int(df_duplicatas["Grupo"].nunique()) if not df_duplicatas.empty else 0
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Anomalias de data", len(df_anomalias))
        with col2:
            st.metric("Lançamentos em grupos duplicados", len(df_duplicatas))
        with col3:
            st.metric("Grupos de duplicatas", n_grupos)

        st.markdown("---")
        _render_tabela_anomalias(df_anomalias)

        st.markdown("---")
        _render_tabela_duplicatas(df_duplicatas)


if __name__ == "__main__":
    render_anomalies_page()
