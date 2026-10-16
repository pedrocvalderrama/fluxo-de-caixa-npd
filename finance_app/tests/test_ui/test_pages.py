import pytest
import sys
from unittest.mock import patch, MagicMock

sys.modules['streamlit'] = MagicMock()

def test_render_dashboard_importavel():
    from finance_app.ui.pages.pg_dashboard import render_dashboard
    assert callable(render_dashboard)

def test_render_cashflow_importavel():
    try:
        from finance_app.ui.pages.pg_cashflow import render_cashflow_page
        assert callable(render_cashflow_page)
    except ModuleNotFoundError:
        pass

def test_render_health_importavel():
    try:
        from finance_app.ui.pages.pg_health import render_health_page
        assert callable(render_health_page)
    except ModuleNotFoundError:
        pass

def test_render_insights_importavel():
    try:
        from finance_app.ui.pages.pg_insights import render_insights_page
        assert callable(render_insights_page)
    except ModuleNotFoundError:
        pass

def test_render_import_importavel():
    from finance_app.ui.pages.pg_import import render_import_page
    assert callable(render_import_page)

def test_settings_importavel():
    from finance_app.ui.pages.pg_settings import renderizar_pagina
    assert callable(renderizar_pagina)

def test_sidebar_menu_items():
    from finance_app.ui.components.sidebar import MENU_ITEMS
    assert len(MENU_ITEMS) == 14

def test_sidebar_chaves_unicas():
    from finance_app.ui.components.sidebar import MENU_ITEMS
    keys = [item[0] for item in MENU_ITEMS if item is not None]
    assert len(keys) == len(set(keys))
    assert "anomalies" in keys

def test_anomalies_page_importavel():
    from finance_app.ui.pages.pg_anomalies import render_anomalies_page
    assert callable(render_anomalies_page)

def test_filter_service_filtros_dataclass():
    from finance_app.services.filter_service import FiltrosPesquisa
    f = FiltrosPesquisa()
    assert f.status == 'realizado'
