"""
Renderização de tabelas do fluxo de caixa.
"""
import pandas as pd
import streamlit as st


_COLUMN_CONFIG = None


def _column_config():
    global _COLUMN_CONFIG
    if _COLUMN_CONFIG is None:
        _COLUMN_CONFIG = {
            "#": st.column_config.TextColumn("#", width="small"),
            "Conta": st.column_config.TextColumn("Conta / Banco"),
            "Saldo Inicial": st.column_config.NumberColumn("Saldo Inicial", format="R$ %.2f"),
            "Entradas": st.column_config.NumberColumn("Entradas", format="R$ %.2f"),
            "Saídas": st.column_config.NumberColumn("Saídas", format="R$ %.2f"),
            "Resultado": st.column_config.NumberColumn("Resultado", format="R$ %.2f"),
        }
    return _COLUMN_CONFIG


def _grupos_por_empresa(df: pd.DataFrame) -> list[tuple[pd.Series, pd.DataFrame]]:
    """Separa o DataFrame hierárquico em (linha_empresa, df_bancos) por empresa."""
    grupos = []
    if df is None or df.empty or "#" not in df.columns:
        return grupos

    emp_mask = ~df["#"].astype(str).str.contains(r"\.", regex=True)
    empresas = df[emp_mask]

    for _, emp_row in empresas.iterrows():
        prefixo = str(emp_row["#"])
        bancos = df[df["#"].astype(str).str.match(rf"^{prefixo}\.\d+$")].copy()
        grupos.append((emp_row, bancos))
    return grupos


def render_resumo_empresa_banco(df: pd.DataFrame, titulo: str = "🏦 Resultado por Empresa e Banco") -> None:
    """
    Exibe o resumo com cada empresa em um bloco separado para facilitar a leitura.
    """
    if df is None or df.empty:
        return

    st.subheader(titulo)
    st.caption(
        "Cada empresa lista os 3 bancos. "
        "Saldo Inicial vem do quadro manual; Entradas/Saídas vêm dos lançamentos. "
        "Resultado = Saldo Inicial + Entradas + Saídas. "
        "Lançamentos sem coluna Banco na planilha ficam em \"Não informado\"."
    )

    grupos = _grupos_por_empresa(df)
    col_cfg = _column_config()
    if not grupos:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=(len(df) + 1) * 37 + 8,
            column_config=col_cfg,
        )
        return

    for i, (emp_row, bancos) in enumerate(grupos):
        nome = str(emp_row.get("Conta", "")).strip()
        with st.container(border=True):
            st.markdown(f"**{emp_row['#']} — {nome}**")
            bloco = pd.concat(
                [emp_row.to_frame().T, bancos],
                ignore_index=True,
            )
            st.dataframe(
                bloco,
                use_container_width=True,
                hide_index=True,
                height=(len(bloco) + 1) * 37 + 8,
                column_config=col_cfg,
            )
        if i < len(grupos) - 1:
            st.markdown("")


def render_fluxo_diario_tabela(
    df: pd.DataFrame,
    session=None,
    filtros=None,
    key: str = "fluxo_diario",
) -> None:
    """Tabela de fluxo diário. Clique em Saídas para ver os lançamentos do dia."""
    from finance_app.utils.dates import formatar_data, formatar_datas_dataframe

    st.subheader("📅 Fluxo Diário")
    if df is None or df.empty:
        st.info("Nenhum dado encontrado para o fluxo diário com os filtros selecionados.")
        return

    # Mantém datas originais para lookup; exibe formatado
    df_base = df.reset_index(drop=True).copy()
    df_exibir = formatar_datas_dataframe(df_base, colunas=["Data"]).copy()

    def _estilo_resultado(val):
        try:
            numero = float(val)
        except (TypeError, ValueError):
            return ""
        if numero > 0:
            return "color: #86efac; font-weight: 600"
        if numero < 0:
            return "color: #fca5a5; font-weight: 600"
        return "color: #d4d4d8"

    def _estilo_saldo(val):
        try:
            numero = float(val)
        except (TypeError, ValueError):
            return ""
        if numero > 0:
            return "background-color: rgba(34, 197, 94, 0.22); color: #86efac; font-weight: 600"
        if numero < 0:
            return "background-color: rgba(239, 68, 68, 0.22); color: #fca5a5; font-weight: 600"
        return "color: #d4d4d8"

    formatters = {}
    for col in df_exibir.select_dtypes(include=["float64", "int64", "float32", "int32"]).columns:
        formatters[col] = "R$ {:,.2f}"

    styled = df_exibir.style.format(formatters, na_rep="")
    try:
        if "Resultado Diário" in df_exibir.columns:
            styled = styled.map(_estilo_resultado, subset=["Resultado Diário"])
        if "Saldo Inicial" in df_exibir.columns:
            styled = styled.map(_estilo_saldo, subset=["Saldo Inicial"])
        if "Saldo Acumulado" in df_exibir.columns:
            styled = styled.map(_estilo_saldo, subset=["Saldo Acumulado"])
    except Exception:
        if "Resultado Diário" in df_exibir.columns:
            styled = styled.applymap(_estilo_resultado, subset=["Resultado Diário"])
        if "Saldo Inicial" in df_exibir.columns:
            styled = styled.applymap(_estilo_saldo, subset=["Saldo Inicial"])
        if "Saldo Acumulado" in df_exibir.columns:
            styled = styled.applymap(_estilo_saldo, subset=["Saldo Acumulado"])

    pode_detalhar = session is not None and filtros is not None and "Saídas" in df_exibir.columns
    if pode_detalhar:
        st.caption("Clique no valor de **Saídas** de um dia para ver os lançamentos que formam o total.")

    altura = min(600, (min(len(df_exibir), 15) + 1) * 37 + 8)
    if pode_detalhar:
        evento = st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            height=altura,
            key=key,
            on_select="rerun",
            selection_mode="single-cell",
        )
        _render_detalhe_saidas_fluxo(df_base, evento, session, filtros)
    else:
        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            height=altura,
            key=key,
        )


def _render_detalhe_saidas_fluxo(df_base: pd.DataFrame, evento, session, filtros) -> None:
    """Mostra as movimentações de saída do dia selecionado na célula Saídas."""
    from datetime import date as date_cls

    from finance_app.services.cashflow_service import obter_saidas_do_dia
    from finance_app.utils.dates import formatar_data

    try:
        celulas = list(evento.selection.cells or [])
    except Exception:
        celulas = []

    if not celulas:
        return

    linha_idx, coluna = celulas[0]
    if coluna != "Saídas":
        st.info("Selecione uma célula da coluna **Saídas** para ver o detalhamento.")
        return

    if linha_idx < 0 or linha_idx >= len(df_base):
        return

    data_ref = df_base.iloc[linha_idx]["Data"]
    if not isinstance(data_ref, date_cls):
        data_ref = pd.Timestamp(data_ref).date()

    total_tabela = float(df_base.iloc[linha_idx]["Saídas"] or 0.0)
    df_saidas = obter_saidas_do_dia(session, filtros, data_ref)

    st.markdown("---")
    st.subheader(f"📤 Saídas de {formatar_data(data_ref)}")

    if df_saidas is None or df_saidas.empty:
        st.info("Nenhuma saída encontrada para este dia com os filtros atuais.")
        return

    total_detalhe = float(df_saidas["valor"].sum())
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Lançamentos", f"{len(df_saidas):,}".replace(",", "."))
    with c2:
        st.metric("Total das saídas", f"R$ {total_detalhe:,.2f}")

    if abs(total_detalhe - total_tabela) > 0.01:
        st.caption(f"Referência na tabela do dia: R$ {total_tabela:,.2f}.")

    st.dataframe(
        df_saidas,
        use_container_width=True,
        hide_index=True,
        height=min(400, (min(len(df_saidas), 12) + 1) * 37 + 8),
        column_config={
            "Empresa": st.column_config.TextColumn("Empresa"),
            "Banco": st.column_config.TextColumn("Banco"),
            "vencimento": st.column_config.TextColumn("Vencimento"),
            "titular": st.column_config.TextColumn("Titular"),
            "tipo": st.column_config.TextColumn("Tipo"),
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
        },
    )



def render_movimentacoes_simplificadas(df: pd.DataFrame) -> None:
    """Tabela enxuta de lançamentos para a página de Fluxo de Caixa."""
    st.subheader("📋 Lançamentos")
    if df is None or df.empty:
        st.info("Nenhum lançamento encontrado para os filtros selecionados.")
        return

    st.caption(f"Total de registros: {len(df):,}".replace(",", "."))
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=min(600, (min(len(df), 15) + 1) * 37 + 8),
        column_config={
            "Empresa": st.column_config.TextColumn("Empresa"),
            "Banco": st.column_config.TextColumn("Banco"),
            "vencimento": st.column_config.TextColumn("Vencimento"),
            "titular": st.column_config.TextColumn("Titular"),
            "tipo": st.column_config.TextColumn("Tipo"),
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
        },
    )
