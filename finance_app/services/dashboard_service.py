from dataclasses import dataclass, replace
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from finance_app.services.filter_service import FiltrosPesquisa, construir_query_movimentacoes
from finance_app.database.models import Movimentacao, Categoria

@dataclass
class ResumoKPIs:
    """KPIs de fluxo de caixa."""
    total_entradas: float
    total_saidas: float
    resultado: float

def obter_kpis(session: Session, filtros: FiltrosPesquisa) -> ResumoKPIs:
    """Calcula os KPIs básicos para o dashboard."""
    query = construir_query_movimentacoes(filtros)
    
    entradas_query = query.where(Movimentacao.tipo == 'RECEBER').with_only_columns(func.coalesce(func.sum(Movimentacao.valor_absoluto), 0.0))
    saidas_query = query.where(Movimentacao.tipo == 'PAGAR').with_only_columns(func.coalesce(func.sum(Movimentacao.valor), 0.0))
    
    total_entradas = session.scalar(entradas_query) or 0.0
    total_saidas = session.scalar(saidas_query) or 0.0
    
    return ResumoKPIs(
        total_entradas=float(total_entradas),
        total_saidas=float(total_saidas),
        resultado=float(total_entradas + total_saidas)
    )

def obter_top_categorias(session: Session, filtros: FiltrosPesquisa, limite: int = 5) -> dict:
    """Retorna as top categorias de despesa."""
    filtros_pagar = replace(filtros, tipos=['PAGAR'])
    
    query = construir_query_movimentacoes(filtros_pagar)
    
    # Garante que o join com Categoria foi feito para a projeção e ordenação
    if filtros_pagar.grupos_categoria is None:
        query = query.join(Categoria, Movimentacao.categoria_id == Categoria.id)
        
    query = query.with_only_columns(
        Categoria.nome,
        func.sum(Movimentacao.valor_absoluto).label('total_absoluto')
    ).group_by(Categoria.nome).order_by(desc('total_absoluto')).limit(limite)
    
    resultados = session.execute(query).all()
    
    return {row[0]: float(row[1]) for row in resultados}
