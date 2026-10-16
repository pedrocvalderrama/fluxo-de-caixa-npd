"""
Componentes de métricas e KPIs para a interface.
"""
from typing import Any
import streamlit as st
from finance_app.utils.currency import formatar_moeda


def render_kpi_cards(
    entradas: Any,
    saidas: float = 0.0,
    resultado: float = 0.0,
    saldo_inicial: float = 0.0,
    saldo_final: float = 0.0,
) -> None:
    """
    Renderiza os cartões de KPI (Key Performance Indicators) no topo do dashboard.
    Pode receber um objeto ResumoKPIs no primeiro parâmetro ou os valores individuais.
    """
    if hasattr(entradas, "total_entradas"):
        resumo = entradas
        entradas = getattr(resumo, "total_entradas", 0.0)
        saidas = getattr(resumo, "total_saidas", 0.0)
        resultado = getattr(resumo, "resultado", 0.0)

    # Define estilos CSS para os cartões premium dark theme
    st.markdown(
        """
        <style>
        .kpi-card {
            background-color: #1e1e1e;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            text-align: center;
            border-top: 4px solid #333;
            margin-bottom: 10px;
        }
        .kpi-title {
            color: #888;
            font-size: 13px;
            text-transform: uppercase;
            margin-bottom: 8px;
            font-weight: 600;
        }
        .kpi-value {
            font-size: 20px;
            font-weight: bold;
            color: #fff;
        }
        .kpi-positive { color: #4ade80 !important; }
        .kpi-negative { color: #f87171 !important; }
        .kpi-card-entradas { border-top-color: #4ade80; }
        .kpi-card-saidas { border-top-color: #f87171; }
        .kpi-card-resultado { border-top-color: #60a5fa; }
        .kpi-card-saldo { border-top-color: #fbbf24; }
        </style>
    """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown(
            f"""
            <div class="kpi-card kpi-card-saldo">
                <div class="kpi-title">Saldo Inicial</div>
                <div class="kpi-value">{formatar_moeda(saldo_inicial)}</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="kpi-card kpi-card-entradas">
                <div class="kpi-title">Entradas</div>
                <div class="kpi-value kpi-positive">{formatar_moeda(entradas)}</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div class="kpi-card kpi-card-saidas">
                <div class="kpi-title">Saídas</div>
                <div class="kpi-value kpi-negative">{formatar_moeda(saidas)}</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    with col4:
        resultado_class = "kpi-positive" if resultado >= 0 else "kpi-negative"
        st.markdown(
            f"""
            <div class="kpi-card kpi-card-resultado">
                <div class="kpi-title">Resultado</div>
                <div class="kpi-value {resultado_class}">{formatar_moeda(resultado)}</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    with col5:
        saldo_class = "kpi-positive" if saldo_final >= 0 else "kpi-negative"
        st.markdown(
            f"""
            <div class="kpi-card kpi-card-saldo">
                <div class="kpi-title">Saldo Final</div>
                <div class="kpi-value {saldo_class}">{formatar_moeda(saldo_final)}</div>
            </div>
        """,
            unsafe_allow_html=True,
        )
