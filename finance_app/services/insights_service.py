from typing import List, Dict
from sqlalchemy.orm import Session

from finance_app.services.filter_service import FiltrosPesquisa
from finance_app.services import dashboard_service, category_service


def gerar_insights(session: Session, filtros: FiltrosPesquisa) -> List[Dict[str, str]]:
    """
    Gera insights analíticos de negócio baseados nos KPIs e categorias.
    """
    insights = []

    kpis = dashboard_service.obter_kpis(session, filtros)
    receitas = float(getattr(kpis, 'total_entradas', 0.0))
    despesas = float(abs(getattr(kpis, 'total_saidas', 0.0)))

    # Analisar déficit
    if receitas < despesas:
        insights.append({
            'tipo': 'negativo',
            'mensagem': f'Suas despesas (R$ {despesas:,.2f}) superaram as receitas (R$ {receitas:,.2f}). Risco de redução de caixa.'
        })
    elif receitas > despesas and receitas > 0:
        insights.append({
            'tipo': 'positivo',
            'mensagem': f'Desempenho positivo: Receitas excederam despesas em R$ {(receitas - despesas):,.2f}.'
        })
    else:
        insights.append({
            'tipo': 'alerta',
            'mensagem': 'As movimentações estão muito baixas ou o fluxo está zerado no período.'
        })

    # Analisar concentração de despesas
    if despesas > 0:
        try:
            df_cat = category_service.obter_analise_categorias(session, filtros, tipo_movimento='PAGAR')
            if not df_cat.empty:
                for _, row in df_cat.iterrows():
                    pct = float(row.get('Percentual do Total', 0.0))
                    nome_cat = str(row.get('Categoria', 'Desconhecida'))
                    if pct > 30.0:
                        insights.append({
                            'tipo': 'alerta',
                            'mensagem': f'Risco de Concentração: A categoria "{nome_cat}" representa {pct:.1f}% de todas as despesas.'
                        })
        except Exception:
            pass

    # Assegura o mínimo de 2 insights na saída
    if len(insights) < 2:
        insights.append({
            'tipo': 'positivo',
            'mensagem': 'A estrutura de custos está bem distribuída e não apresenta grandes concentrações.'
        })

    return insights
