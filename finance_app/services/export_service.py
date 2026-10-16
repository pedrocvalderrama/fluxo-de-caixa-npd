import io
import pandas as pd
from sqlalchemy.orm import Session

from finance_app.services.filter_service import FiltrosPesquisa, construir_query_movimentacoes
from finance_app.utils.dates import formatar_datas_dataframe


def exportar_para_excel(session: Session, filtros: FiltrosPesquisa) -> bytes:
    """
    Executa a query com os filtros informados e exporta o resultado para um arquivo Excel em memória.
    Retorna os bytes do arquivo gerado para uso no st.download_button.
    """
    query = construir_query_movimentacoes(filtros)
    df = pd.read_sql(query, session.bind)

    if df.empty:
        return b""

    if 'id' in df.columns:
        df = df.drop(columns=['id', 'importacao_id', 'raw_id', 'hash_registro'], errors='ignore')

    df = formatar_datas_dataframe(df)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Movimentacoes')

    return output.getvalue()


def exportar_para_csv(session: Session, filtros: FiltrosPesquisa) -> bytes:
    """
    Exporta o resultado filtrado para CSV.
    """
    query = construir_query_movimentacoes(filtros)
    df = pd.read_sql(query, session.bind)

    if df.empty:
        return b""

    if 'id' in df.columns:
        df = df.drop(columns=['id', 'importacao_id', 'raw_id', 'hash_registro'], errors='ignore')

    df = formatar_datas_dataframe(df)

    output = io.BytesIO()
    df.to_csv(output, index=False, sep=';', decimal=',', encoding='utf-8-sig')
    return output.getvalue()
