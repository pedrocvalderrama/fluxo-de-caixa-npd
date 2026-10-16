"""
Serviço para análises de categorias de movimentação.
"""
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func

from finance_app.database.models import Movimentacao, Categoria
from finance_app.services.filter_service import FiltrosPesquisa, construir_query_movimentacoes


def obter_analise_categorias(
    session: Session, 
    filtros: FiltrosPesquisa, 
    tipo_movimento: str = 'PAGAR'
) -> pd.DataFrame:
    """
    Retorna um DataFrame com a análise de valores absolutos por grupo e categoria.
    
    Args:
        session: Sessão do SQLAlchemy.
        filtros: Filtros para a pesquisa de movimentações.
        tipo_movimento: Tipo de movimento a considerar (ex: 'PAGAR', 'RECEBER', 'AMBOS').
        
    Returns:
        pd.DataFrame com colunas: 'Grupo', 'Categoria', 'Valor Absoluto', 'Percentual do Total'
    """
    query = construir_query_movimentacoes(filtros)
    
    # Adicionando o JOIN com Categoria explicitamente para a projeção, caso não exista nos filtros
    if filtros.grupos_categoria is None:
        query = query.join(Categoria, Movimentacao.categoria_id == Categoria.id)
        
    if tipo_movimento != 'AMBOS':
        query = query.where(Movimentacao.tipo == tipo_movimento)
        
    # Agrupando por grupo e categoria
    query = query.with_only_columns(
        Categoria.grupo.label('Grupo'),
        Categoria.nome.label('Categoria'),
        func.sum(Movimentacao.valor_absoluto).label('Valor Absoluto')
    ).group_by(
        Categoria.grupo,
        Categoria.nome
    )
    
    resultados = session.execute(query).all()
    
    if not resultados:
        return pd.DataFrame(columns=['Grupo', 'Categoria', 'Valor Absoluto', 'Percentual do Total'])
        
    df = pd.DataFrame(resultados)
    
    total = df['Valor Absoluto'].sum()
    
    if total > 0:
        df['Percentual do Total'] = (df['Valor Absoluto'] / total) * 100
    else:
        df['Percentual do Total'] = 0.0
        
    # Ordenar por Valor Absoluto decrescente
    df = df.sort_values(by='Valor Absoluto', ascending=False).reset_index(drop=True)
    
    return df
