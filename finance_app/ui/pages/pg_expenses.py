"""
Página de Análise de Saídas (Despesas).
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from finance_app.database.connection import SessionLocal
from finance_app.database.models import Empresa, Categoria
from finance_app.ui.components.filters import render_global_filters
from finance_app.services import filter_service
from finance_app.utils.dates import formatar_datas_dataframe, PLOTLY_DATE_FORMAT
from finance_app.utils.currency import formatar_moeda


def renderizar_pagina():
    """Renderiza a página de Saídas (Despesas)."""
    st.markdown("## 📉 Análise de Saídas / Despesas")
    st.markdown("Visão focada na evolução dos custos, estudo por centro de custo e principais fornecedores.")
    st.divider()

    with SessionLocal() as session:
        filtros = render_global_filters(session)
        # Forçar o tipo apenas para PAGAR
        filtros.tipos = ['PAGAR']

        query = filter_service.construir_query_movimentacoes(filtros)
        df = pd.read_sql(query, session.bind)

        if df.empty:
            st.info("Nenhuma saída registrada para os filtros selecionados.")
            return

        # Converter colunas numéricas
        if 'valor_absoluto' not in df.columns and 'valor' in df.columns:
            df['valor_absoluto'] = df['valor'].abs()

        # Mapear empresas e categorias para nomes amigáveis
        mapa_emp = {e.id: e.nome for e in session.query(Empresa).all()}
        mapa_cat = {c.id: c.nome for c in session.query(Categoria).all()}
        df['empresa_nome'] = df['empresa_id'].map(mapa_emp).fillna('-')
        df['categoria_nome'] = df['categoria_id'].map(mapa_cat).fillna('Geral')
        df['status_desc'] = df['em_aberto'].map({True: 'Em Aberto', False: 'Pago'})
        df['centro_custo_exib'] = df['centro_custo'].fillna('Não Informado').astype(str).str.strip()
        df['centro_custo_exib'] = df['centro_custo_exib'].replace({'': 'Não Informado', 'None': 'Não Informado', 'nan': 'Não Informado'})

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### Evolução das Saídas ao Longo do Tempo")
            col_data = 'vencimento'
            if col_data in df.columns and df[col_data].notnull().any():
                df_temp = df.groupby(col_data)['valor_absoluto'].sum().reset_index()
                fig = px.line(
                    df_temp,
                    x=col_data,
                    y='valor_absoluto',
                    title="Despesas por Data",
                    labels={'valor_absoluto': 'Total (R$)', col_data: 'Data'},
                    template="plotly_dark"
                )
                fig.update_traces(line_color="#f87171")
                fig.update_layout(
                    xaxis=dict(tickformat=PLOTLY_DATE_FORMAT, hoverformat=PLOTLY_DATE_FORMAT),
                    margin=dict(l=10, r=10, t=40, b=10)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem dados de datas para exibir a evolução temporal.")

        with col2:
            st.markdown("### Top 10 Fornecedores / Titulares")
            if 'titular' in df.columns:
                top_fornecedores = df.groupby('titular')['valor_absoluto'].sum().nlargest(10).reset_index()
                fig_top = px.bar(
                    top_fornecedores,
                    x='valor_absoluto',
                    y='titular',
                    orientation='h',
                    title="Maiores Pagamentos",
                    labels={'valor_absoluto': 'Total (R$)', 'titular': 'Titular'},
                    template="plotly_dark"
                )
                fig_top.update_traces(marker_color="#f87171")
                fig_top.update_layout(yaxis={'categoryorder': 'total ascending'}, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_top, use_container_width=True)

        # ── Estudo por Centro de Custo (Largura Total) ────────────────────
        st.markdown("---")
        st.markdown("### 🏢 Gastos por Centro de Custo / Setor")
        st.caption("Clique no setor ou em qualquer linha da tabela para explodir e ver os lançamentos que formam o total.")

        df_cc_grp = (
            df.groupby('centro_custo_exib')['valor_absoluto']
            .agg(['sum', 'count'])
            .reset_index()
            .rename(columns={
                'centro_custo_exib': 'Centro de Custo / Setor',
                'count': 'Quantidade de Títulos',
                'sum': 'Total (R$)'
            })
            .sort_values('Total (R$)', ascending=False)
            .reset_index(drop=True)
        )

        # Opção de ocultar 'Não Informado'
        tem_nao_inf = 'Não Informado' in df_cc_grp['Centro de Custo / Setor'].values
        ocultar_nao_inf = False
        if tem_nao_inf and len(df_cc_grp) > 1:
            ocultar_nao_inf = st.checkbox(
                "Ocultar lançamentos sem centro de custo (Não Informado)",
                value=False,
                key="chk_ocultar_nao_inf"
            )
            if ocultar_nao_inf:
                df_cc_grp = df_cc_grp[df_cc_grp['Centro de Custo / Setor'] != 'Não Informado'].reset_index(drop=True)

        if df_cc_grp.empty:
            st.info("Nenhum lançamento com centro de custo encontrado para os filtros selecionados.")
        else:
            # Chave dinâmica para reset de seleção se o usuário fechar
            cc_key = f"df_cc_resumo_tabela_{st.session_state.get('cc_table_key_idx', 0)}"
            altura_cc = min(400, (len(df_cc_grp) + 1) * 36 + 15)

            evento_cc = st.dataframe(
                df_cc_grp,
                use_container_width=True,
                hide_index=True,
                height=altura_cc,
                key=cc_key,
                on_select="rerun",
                selection_mode=["single-row", "single-cell"],
                column_config={
                    "Centro de Custo / Setor": st.column_config.TextColumn("Centro de Custo / Setor"),
                    "Quantidade de Títulos": st.column_config.NumberColumn("Quantidade de Títulos", format="%d"),
                    "Total (R$)": st.column_config.NumberColumn("Total (R$)", format="R$ %.2f"),
                }
            )

            # Detectar seleção na tabela (linha ou célula)
            setor_selecionado = None
            if evento_cc and hasattr(evento_cc, "selection"):
                rows = getattr(evento_cc.selection, "rows", []) or []
                if len(rows) > 0:
                    idx_linha = rows[0]
                    if 0 <= idx_linha < len(df_cc_grp):
                        setor_selecionado = df_cc_grp.iloc[idx_linha]["Centro de Custo / Setor"]
                else:
                    cells = getattr(evento_cc.selection, "cells", []) or []
                    if len(cells) > 0:
                        celula = cells[0]
                        idx_linha = celula[0] if isinstance(celula, (list, tuple)) else getattr(celula, "row", None)
                        if idx_linha is not None and 0 <= idx_linha < len(df_cc_grp):
                            setor_selecionado = df_cc_grp.iloc[idx_linha]["Centro de Custo / Setor"]

            # ── Tabela Explodida do Centro de Custo Selecionado ──────────────
            if setor_selecionado:
                with st.container(border=True):
                    cab_col1, cab_col2 = st.columns([5, 1])
                    with cab_col1:
                        st.markdown(f"#### 💥 Despesas Explodidas: **{setor_selecionado}**")
                    with cab_col2:
                        if st.button("✖ Fechar", key="btn_fechar_drilldown", use_container_width=True):
                            st.session_state["cc_table_key_idx"] = st.session_state.get("cc_table_key_idx", 0) + 1
                            st.rerun()

                    df_detalhe = df[df['centro_custo_exib'] == setor_selecionado].copy()
                    total_setor = df_detalhe['valor_absoluto'].sum()
                    total_geral = df['valor_absoluto'].sum()
                    pct_geral = (total_setor / total_geral * 100) if total_geral > 0 else 0

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Total do Setor", formatar_moeda(total_setor))
                    m2.metric("Qtd. Títulos", f"{len(df_detalhe)}")
                    m3.metric("Ticket Médio", formatar_moeda(total_setor / len(df_detalhe) if len(df_detalhe) > 0 else 0))
                    m4.metric("% das Saídas", f"{pct_geral:.1f}%")

                    df_detalhe_tabela = df_detalhe[[
                        'vencimento', 'documento', 'titular', 'categoria_nome', 'empresa_nome', 'valor_absoluto', 'status_desc', 'data_transacao'
                    ]].rename(columns={
                        'vencimento': 'Vencimento',
                        'documento': 'Doc / AP',
                        'titular': 'Fornecedor / Titular',
                        'categoria_nome': 'Categoria',
                        'empresa_nome': 'Empresa',
                        'valor_absoluto': 'Valor (R$)',
                        'status_desc': 'Status',
                        'data_transacao': 'Data Pagamento'
                    }).sort_values('Vencimento', ascending=False)

                    st.dataframe(
                        formatar_datas_dataframe(df_detalhe_tabela),
                        use_container_width=True,
                        hide_index=True,
                        height=min(450, (min(len(df_detalhe_tabela), 10) + 1) * 37 + 8),
                        column_config={
                            "Valor (R$)": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f")
                        }
                    )

        st.markdown("---")
        st.markdown("### 📋 Tabela Geral de Lançamentos de Saída")
        cols_gerais = [
            'vencimento', 'documento', 'titular', 'centro_custo_exib', 'categoria_nome', 'empresa_nome', 'valor_absoluto', 'status_desc', 'data_transacao'
        ]
        df_exibir_geral = df[cols_gerais].rename(columns={
            'vencimento': 'Vencimento',
            'documento': 'Doc / AP',
            'titular': 'Fornecedor / Titular',
            'centro_custo_exib': 'Centro de Custo',
            'categoria_nome': 'Categoria',
            'empresa_nome': 'Empresa',
            'valor_absoluto': 'Valor (R$)',
            'status_desc': 'Status',
            'data_transacao': 'Data Pagamento'
        }).sort_values('Vencimento', ascending=False)

        st.dataframe(
            formatar_datas_dataframe(df_exibir_geral),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Valor (R$)": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f")
            }
        )


if __name__ == "__main__":
    renderizar_pagina()
