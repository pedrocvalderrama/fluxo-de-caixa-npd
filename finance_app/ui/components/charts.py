"""
Componentes de gráficos para a interface usando Plotly.
"""
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, Any
from finance_app.utils.dates import PLOTLY_DATE_FORMAT

def render_cashflow_chart(df: pd.DataFrame) -> None:
    """
    Renderiza um gráfico combinado com o saldo acumulado em linha
    e entradas/saídas em barras finas sobrepostas.
    """
    if df.empty:
        st.warning("Sem dados para exibir no gráfico.")
        return
        
    fig = go.Figure()
    
    # Adicionar barras de Entradas
    if 'Entradas' in df.columns:
        fig.add_trace(
            go.Bar(
                x=df['Data'],
                y=df['Entradas'],
                name="Entradas",
                marker_color="#4ade80",
                opacity=0.7,
                # Evitar conflitos visuais se as barras forem muito largas
            )
        )
        
    # Adicionar barras de Saídas
    col_saidas = 'Saídas' if 'Saídas' in df.columns else ('Saidas' if 'Saidas' in df.columns else None)
    if col_saidas:
        # Inverter sinal das saídas para irem para baixo no gráfico, se estiverem positivas
        y_saidas = df[col_saidas]
        if (y_saidas > 0).any():
            y_saidas = y_saidas * -1
            
        fig.add_trace(
            go.Bar(
                x=df['Data'],
                y=y_saidas,
                name="Saídas",
                marker_color="#f87171",
                opacity=0.7,
            )
        )
        
    # Adicionar linha de Saldo Acumulado
    if 'Saldo Acumulado' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['Data'],
                y=df['Saldo Acumulado'],
                name="Saldo Acumulado",
                mode="lines+markers",
                line=dict(color="#60a5fa", width=3),
                marker=dict(size=6, color="#60a5fa")
            )
        )
        
    # Layout premium dark theme
    fig.update_layout(
        title="Evolução do Fluxo de Caixa",
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        barmode="overlay",  # Permite sobreposição se necessário, ou usar 'relative'
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        xaxis=dict(showgrid=False, tickformat=PLOTLY_DATE_FORMAT, hoverformat=PLOTLY_DATE_FORMAT),
        yaxis=dict(showgrid=True, gridcolor="#333", zerolinecolor="#555")
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_category_bar_chart(categorias_dict: Dict[str, float]) -> None:
    """
    Renderiza um gráfico de barras horizontais simples para os tops de despesas.
    """
    if not categorias_dict:
        st.warning("Sem dados de categorias para exibir.")
        return
        
    # Converter dicionário para DataFrame
    df_cat = pd.DataFrame(list(categorias_dict.items()), columns=['Categoria', 'Valor'])
    
    # Considerar apenas valores de despesas (negativos ou já convertidos)
    df_cat['Valor_Abs'] = df_cat['Valor'].abs()
    
    # Ordenar pelos maiores valores absolutos e pegar os Top 10
    df_cat = df_cat.sort_values(by='Valor_Abs', ascending=True).tail(10)
    
    fig = px.bar(
        df_cat,
        x='Valor_Abs',  # Mostrar o valor absoluto para ficar positivo no gráfico
        y='Categoria',
        orientation='h',
        title="Top Despesas por Categoria",
        color_discrete_sequence=["#f87171"]
    )
    
    # Layout premium dark theme
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=60, b=40),
        xaxis=dict(showgrid=True, gridcolor="#333", zerolinecolor="#555", title="Valor"),
        yaxis=dict(showgrid=False, title="")
    )
    
    st.plotly_chart(fig, use_container_width=True)
