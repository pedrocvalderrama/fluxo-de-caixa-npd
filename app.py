"""
Ponto de entrada principal da aplicação Streamlit.
Sistema de Gestão e Análise Financeira.
"""
import sys
from pathlib import Path

# Garantir que o pacote finance_app seja encontrado
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import streamlit as st
from finance_app.config.settings import settings
from finance_app.database.connection import init_db

# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title=settings.APP_NAME,
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": f"**{settings.APP_NAME}** v{settings.APP_VERSION}",
    },
)

# ── Inicializar banco de dados ───────────────────────────────────────────────
# Sem cache: create_all + migrações leves precisam rodar a cada restart
# (ex.: coluna banco_id em bases já existentes).
settings.ensure_dirs()
init_db()

# ── CSS Global ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Importar fonte Inter do Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Remover padding padrão do header */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1rem;
    }

    /* Cards de métricas */
    [data-testid="metric-container"] {
        background: #1e2130;
        border: 1px solid #2d3250;
        border-radius: 12px;
        padding: 1rem;
    }
    [data-testid="metric-container"] label {
        color: #8b92a5 !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: #e8eaf6 !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #13151f;
        border-right: 1px solid #2d3250;
    }

    /* Botões primários */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        border-radius: 8px;
        color: white;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s ease;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }

    /* Tabelas */
    .dataframe {
        font-size: 0.85rem !important;
    }

    /* Remover footer do Streamlit */
    footer { visibility: hidden; }

    /* Divisor */
    hr {
        border-color: #2d3250;
        margin: 1rem 0;
    }

    /* Títulos de seção */
    .section-title {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #8b92a5;
        margin: 1.5rem 0 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ── Roteamento de páginas ────────────────────────────────────────────────────
from finance_app.ui.components.sidebar import renderizar_sidebar

pagina = renderizar_sidebar()

# Importar e renderizar a página selecionada
if pagina == "dashboard":
    from finance_app.ui.pages.pg_dashboard import render_dashboard
    render_dashboard()
elif pagina == "cashflow":
    from finance_app.ui.pages.pg_cashflow import render_cashflow_page
    render_cashflow_page()
elif pagina == "movements":
    from finance_app.ui.pages.pg_movements import renderizar_pagina
    renderizar_pagina()
elif pagina == "income":
    from finance_app.ui.pages.pg_income import renderizar_pagina
    renderizar_pagina()
elif pagina == "expenses":
    from finance_app.ui.pages.pg_expenses import renderizar_pagina
    renderizar_pagina()
elif pagina == "categories":
    from finance_app.ui.pages.pg_categories import renderizar_pagina
    renderizar_pagina()
elif pagina == "comparison":
    from finance_app.ui.pages.pg_comparison import renderizar_pagina
    renderizar_pagina()
elif pagina == "reports":
    from finance_app.ui.pages.pg_reports import renderizar_pagina
    renderizar_pagina()
elif pagina == "health":
    from finance_app.ui.pages.pg_health import render_health_page
    render_health_page()
elif pagina == "insights":
    from finance_app.ui.pages.pg_insights import render_insights_page
    render_insights_page()
elif pagina == "anomalies":
    from finance_app.ui.pages.pg_anomalies import render_anomalies_page
    render_anomalies_page()
elif pagina == "import":
    from finance_app.ui.pages.pg_import import render_import_page
    render_import_page()
elif pagina == "settings":
    from finance_app.ui.pages.pg_settings import renderizar_pagina
    renderizar_pagina()
else:
    from finance_app.ui.pages.pg_dashboard import render_dashboard
    render_dashboard()
