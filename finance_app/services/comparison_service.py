"""
Serviço para comparações de períodos e KPIs.
"""
from typing import Optional
from sqlalchemy.orm import Session

from finance_app.services.filter_service import FiltrosPesquisa
from finance_app.services.dashboard_service import obter_kpis
from finance_app.utils.currency import variacao_percentual


def comparar_periodos(
    session: Session, 
    filtros_base: FiltrosPesquisa, 
    filtros_comparacao: FiltrosPesquisa
) -> dict:
    """
    Compara os KPIs de dois períodos ou filtros distintos, 
    calculando as variações absolutas e percentuais.
    
    Args:
        session: Sessão do SQLAlchemy.
        filtros_base: Filtros do período base (atual).
        filtros_comparacao: Filtros do período a comparar (anterior).
        
    Returns:
        Dicionário com os resultados da comparação (receitas, despesas, resultado).
    """
    kpis_base = obter_kpis(session, filtros_base)
    kpis_comp = obter_kpis(session, filtros_comparacao)
    
    var_abs_receitas = kpis_base.total_entradas - kpis_comp.total_entradas
    var_pct_receitas = variacao_percentual(kpis_base.total_entradas, kpis_comp.total_entradas)
    
    var_abs_despesas = kpis_base.total_saidas - kpis_comp.total_saidas
    var_pct_despesas = variacao_percentual(kpis_base.total_saidas, kpis_comp.total_saidas)
    
    var_abs_resultado = kpis_base.resultado - kpis_comp.resultado
    var_pct_resultado = variacao_percentual(kpis_base.resultado, kpis_comp.resultado)
    
    return {
        'receitas': {
            'base': kpis_base.total_entradas,
            'comp': kpis_comp.total_entradas,
            'var_abs': var_abs_receitas,
            'var_pct': var_pct_receitas
        },
        'despesas': {
            'base': kpis_base.total_saidas,
            'comp': kpis_comp.total_saidas,
            'var_abs': var_abs_despesas,
            'var_pct': var_pct_despesas
        },
        'resultado': {
            'base': kpis_base.resultado,
            'comp': kpis_comp.resultado,
            'var_abs': var_abs_resultado,
            'var_pct': var_pct_resultado
        }
    }
