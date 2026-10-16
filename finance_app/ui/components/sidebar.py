"""
Componente de barra lateral (sidebar) com menu de navegação.
"""
import streamlit as st
from typing import Optional


# Mapeamento: chave interna → (label, ícone)
MENU_ITEMS = [
    ("dashboard",   "📊", "Dashboard"),
    ("cashflow",    "💰", "Fluxo de Caixa"),
    ("movements",   "📋", "Movimentações"),
    ("income",      "📈", "Entradas"),
    ("expenses",    "📉", "Saídas"),
    ("categories",  "🏷️", "Categorias"),
    ("comparison",  "🔄", "Comparação"),
    ("reports",     "📄", "Relatórios"),
    ("health",      "❤️", "Saúde Financeira"),
    ("insights",    "💡", "Insights"),
    ("anomalies",   "⚠️", "Anomalias / Duplicatas"),
    None,  # separador
    ("import",      "📥", "Importar Excel"),
    ("settings",    "⚙️", "Configurações"),
]


def renderizar_sidebar() -> str:
    """
    Renderiza a barra lateral com navegação e retorna a chave da página selecionada.
    
    Returns:
        Chave da página ativa (ex: 'dashboard', 'cashflow', etc.)
    """
    with st.sidebar:
        # ── Logo / Header ────────────────────────────────────────
        st.markdown("""
        <div style="
            padding: 1rem 0 1.5rem 0;
            text-align: center;
            border-bottom: 1px solid #2d3250;
            margin-bottom: 0.5rem;
        ">
            <div style="font-size: 2rem; margin-bottom: 0.25rem;">💰</div>
            <div style="
                font-size: 1rem;
                font-weight: 700;
                color: #e8eaf6;
                line-height: 1.2;
            ">FinanceApp</div>
            <div style="
                font-size: 0.7rem;
                color: #8b92a5;
                margin-top: 0.25rem;
            ">Sistema de Gestão Financeira</div>
        </div>
        """, unsafe_allow_html=True)

        # ── Estado da sessão ─────────────────────────────────────
        if "pagina_ativa" not in st.session_state:
            st.session_state.pagina_ativa = "dashboard"

        pagina_ativa = st.session_state.pagina_ativa

        # ── Menu ─────────────────────────────────────────────────
        st.markdown("""
        <div class="section-title" style="
            font-size: 0.65rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #8b92a5;
            padding: 0.5rem 0 0.25rem 0;
        ">Análise</div>
        """, unsafe_allow_html=True)

        pagina_selecionada: Optional[str] = None

        secao_import = False
        for item in MENU_ITEMS:
            if item is None:
                # Separador antes das ferramentas
                st.markdown("""
                <div class="section-title" style="
                    font-size: 0.65rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.1em;
                    color: #8b92a5;
                    padding: 1rem 0 0.25rem 0;
                    border-top: 1px solid #2d3250;
                    margin-top: 0.5rem;
                ">Ferramentas</div>
                """, unsafe_allow_html=True)
                secao_import = True
                continue

            chave, icone, label = item
            ativo = pagina_ativa == chave

            # CSS condicional para item ativo
            estilo_ativo = (
                "background: linear-gradient(90deg, rgba(102,126,234,0.15), transparent);"
                "border-left: 3px solid #667eea;"
                "color: #c5cae9 !important;"
            ) if ativo else ""

            if st.button(
                f"{icone}  {label}",
                key=f"nav_{chave}",
                use_container_width=True,
                type="secondary",
            ):
                pagina_selecionada = chave

            # Injetar estilo de item ativo via markdown sobreposto
            if ativo:
                st.markdown(f"""
                <style>
                    button[data-testid="baseButton-secondary"][kind="secondary"]:has(+ div > *) {{}}
                    /* Marcar botão ativo */
                    [data-testid="stSidebar"] div:has(> [data-testid="stButton"] > button[key="nav_{chave}"]) {{
                        {estilo_ativo}
                        border-radius: 8px;
                    }}
                </style>
                """, unsafe_allow_html=True)

        # ── Atualizar estado ─────────────────────────────────────
        # Sem st.rerun(): um rerun abortava o script antes de renderizar a
        # página e o Streamlit apagava o session_state dos widgets (filtros/saldo).
        if pagina_selecionada:
            st.session_state.pagina_ativa = pagina_selecionada

        # ── Footer ───────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        _renderizar_status_banco()

    return st.session_state.pagina_ativa


def _renderizar_status_banco() -> None:
    """Renderiza indicador de status do banco de dados."""
    try:
        from finance_app.database.connection import SessionLocal
        from finance_app.database.models import Movimentacao, Importacao
        with SessionLocal() as session:
            n_mov = session.query(Movimentacao).count()
            n_imp = session.query(Importacao).filter(
                Importacao.status == "CONCLUIDA"
            ).count()

        if n_mov > 0:
            st.markdown(f"""
            <div style="
                background: #1a1f35;
                border: 1px solid #2d3250;
                border-radius: 8px;
                padding: 0.75rem;
                font-size: 0.75rem;
                color: #8b92a5;
            ">
                <div style="color: #4caf50; font-weight: 600; margin-bottom: 0.25rem;">
                    ● Banco conectado
                </div>
                <div>{n_mov:,} movimentações</div>
                <div>{n_imp} importação(ões)</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="
                background: #1a1f35;
                border: 1px solid #f57c00;
                border-radius: 8px;
                padding: 0.75rem;
                font-size: 0.75rem;
                color: #8b92a5;
            ">
                <div style="color: #f57c00; font-weight: 600; margin-bottom: 0.25rem;">
                    ● Sem dados
                </div>
                <div>Importe um arquivo Excel<br>para começar.</div>
            </div>
            """, unsafe_allow_html=True)
    except Exception:
        st.markdown("""
        <div style="
            background: #1a1f35;
            border: 1px solid #ef5350;
            border-radius: 8px;
            padding: 0.75rem;
            font-size: 0.75rem;
            color: #8b92a5;
        ">
            <div style="color: #ef5350; font-weight: 600;">
                ● Erro no banco
            </div>
        </div>
        """, unsafe_allow_html=True)
