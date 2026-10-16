import pandas as pd
from sqlalchemy.orm import Session
from finance_app.services.filter_service import FiltrosPesquisa, construir_query_movimentacoes


def detectar_anomalias_transacoes(session: Session, filtros: FiltrosPesquisa) -> pd.DataFrame:
    """
    Identifica possíveis transações anômalas (outliers) que destoam do histórico normal.
    """
    query = construir_query_movimentacoes(filtros)
    df = pd.read_sql(query, session.bind)
    
    if df.empty:
        return df
        
    if 'tipo' in df.columns:
        df_despesas = df[df['tipo'] == 'PAGAR'].copy()
    else:
        return pd.DataFrame()
        
    if df_despesas.empty or len(df_despesas) < 3:
        return pd.DataFrame()

    if 'valor_absoluto' not in df_despesas.columns:
        if 'valor' in df_despesas.columns:
            df_despesas['valor_absoluto'] = df_despesas['valor'].abs()
        else:
            return pd.DataFrame()

    if 'categoria_id' not in df_despesas.columns:
        return pd.DataFrame()
        
    # Calcular média e desvio padrão das despesas por categoria
    stats = df_despesas.groupby('categoria_id')['valor_absoluto'].agg(['mean', 'std']).reset_index()
    stats = stats.rename(columns={'mean': 'valor_medio', 'std': 'valor_std'})
    
    # Mapeia as estatísticas para o DataFrame original
    df_merged = df_despesas.merge(stats, on='categoria_id', how='left')
    df_merged['valor_std'] = df_merged['valor_std'].fillna(0)
    
    # Critério de anomalia: maior que média + 2 desvios padrões E maior que 500
    condicao_anomalia = (
        (df_merged['valor_absoluto'] > (df_merged['valor_medio'] + 2 * df_merged['valor_std'])) &
        (df_merged['valor_absoluto'] > 500)
    )
    
    df_anomalias = df_merged[condicao_anomalia].copy()
    
    if df_anomalias.empty:
        return df_anomalias
        
    df_anomalias['motivo'] = "Valor atipicamente alto para o histórico da categoria"
    
    return df_anomalias
