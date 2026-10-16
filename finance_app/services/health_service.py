from dataclasses import dataclass
from typing import List
from sqlalchemy.orm import Session

from finance_app.services.filter_service import FiltrosPesquisa
from finance_app.services import dashboard_service


@dataclass
class HealthScore:
    score_geral: str
    margem_operacional: float
    indice_liquidez: float
    pontos_fortes: List[str]
    pontos_atencao: List[str]


def calcular_saude_financeira(session: Session, filtros: FiltrosPesquisa) -> HealthScore:
    """
    Calcula o índice de saúde financeira com base na margem operacional e liquidez.
    """
    kpis = dashboard_service.obter_kpis(session, filtros)
    receitas = float(getattr(kpis, 'total_entradas', 0.0))
    despesas = float(abs(getattr(kpis, 'total_saidas', 0.0)))

    # Cálculo da Margem Operacional
    if receitas > 0:
        margem_operacional = ((receitas - despesas) / receitas) * 100.0
    else:
        margem_operacional = 0.0 if despesas == 0 else -100.0

    # Cálculo do Índice de Liquidez
    if despesas > 0:
        indice_liquidez = receitas / despesas
    else:
        indice_liquidez = 999.9 if receitas > 0 else 1.0

    # Determinação do Score Geral
    if margem_operacional > 20:
        score_geral = 'A'
    elif margem_operacional > 5:
        score_geral = 'B'
    elif margem_operacional >= 0:
        score_geral = 'C'
    elif margem_operacional > -10:
        score_geral = 'D'
    else:
        score_geral = 'F'

    pontos_fortes = []
    pontos_atencao = []

    # Geração de pontos fortes e de atenção
    if score_geral in ['A', 'B']:
        pontos_fortes.append("Margem operacional saudável, indicando boa eficiência operacional.")
    elif score_geral in ['D', 'F']:
        pontos_atencao.append("Margem operacional negativa: a operação não está se pagando.")
        
    if indice_liquidez >= 1.2:
        pontos_fortes.append(f"Alta liquidez ({indice_liquidez:.2f}): as entradas cobrem as saídas com folga.")
    elif indice_liquidez < 1.0:
        pontos_atencao.append(f"Atenção: A liquidez está baixa ({indice_liquidez:.2f}), saídas superaram entradas.")

    if not pontos_fortes:
        pontos_fortes.append("Sem pontos de grande destaque, mantenha o equilíbrio atual das contas.")
    if not pontos_atencao:
        pontos_atencao.append("Sem alertas críticos identificados, mas continue monitorando as despesas ativamente.")

    return HealthScore(
        score_geral=score_geral,
        margem_operacional=margem_operacional,
        indice_liquidez=indice_liquidez,
        pontos_fortes=pontos_fortes,
        pontos_atencao=pontos_atencao
    )
