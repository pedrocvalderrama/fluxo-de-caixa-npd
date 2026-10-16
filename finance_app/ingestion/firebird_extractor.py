"""
Extrator de dados financeiros do ERP Sisplan via consultas SQL diretas (Firebird 3).
"""
from datetime import date, datetime
from typing import Optional, List
from decimal import Decimal

from finance_app.ingestion.firebird_client import obter_conexao_sisplan
from finance_app.ingestion.normalizer import (
    MovimentacaoNormalizada,
    calcular_hash_registro,
)
from finance_app.utils.dates import is_data_anomala
from finance_app.utils.formatting import extrair_prefixo_categoria, grupo_categoria
from finance_app.config.bancos import resolver_codigo_banco

# Mapeamento oficial de EMP_ID (Sisplan) para código/nome de Empresa no sistema
EMP_ID_MAP = {
    1: 'NPD',
    2: 'COMPRE',
    3: 'DEMO',
    4: 'CS',
}


def extrair_receber_sisplan(
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    emp_id: Optional[int] = None,
    apenas_duplicatas: bool = True,
    filtrar_devolucoes: bool = True,
) -> List[MovimentacaoNormalizada]:
    """
    Executa a consulta SQL oficial de Contas a Receber na base Firebird do Sisplan
    e converte os resultados diretamente em objetos MovimentacaoNormalizada.

    Parâmetros:
        data_inicio: Data mínima de vencimento (DT_VENCTO). Se None, sem limite inicial.
        data_fim: Data máxima de vencimento (DT_VENCTO). Se None, sem limite final.
        emp_id: Código da empresa (1, 2, 3, 4). Se None, consulta todas as empresas.
        apenas_duplicatas: Se True, filtra por STATUS = 'DUPL'.
        filtrar_devolucoes: Se True, filtra títulos devolvidos (COALESCE(VAL_DEV, 0) <= 0.10).
    """
    sql = """
        SELECT 
            R.EMP_ID,
            R.NUMERO AS DUPLICATA,
            R.PARCELA || '/' || R.QTDEPARCELAS AS PARCELA,
            COALESCE(E.NOME, 'CLIENTE NÃO IDENTIFICADO') AS NOME_CLIENTE,
            R.CLASSE,
            COALESCE(C.DESCRICAO, 'RECEITAS GERAIS') AS NATUREZA,
            R.DT_PAGTO_DUPLI AS DATA_PAGAMENTO,
            R.DT_VENCTO AS DATA_VENCIMENTO,
            COALESCE(R.VALOR2, 0) AS VALOR_PARCELA,
            COALESCE(R.VALOR_PAGO, 0) AS VALOR_PAGO,
            COALESCE(R.VAL_DEV, 0) AS VAL_DEV,
            R.STATUS,
            R.BANCO,
            COALESCE(R.DESCONTO, 0) AS DESCONTO
        FROM RECEBER_001 R
        LEFT JOIN ENTIDADE_001 E ON (R.CODCLI = E.CODCLI)
        LEFT JOIN CLASSE_GER_001 C ON (R.CLASSE = C.CODIGO)
        WHERE 1 = 1
    """

    params = []

    if apenas_duplicatas:
        sql += " AND R.STATUS = 'DUPL'"

    if filtrar_devolucoes:
        sql += " AND COALESCE(R.VAL_DEV, 0) BETWEEN 0.00 AND 0.10"

    if data_inicio is not None:
        sql += " AND R.DT_VENCTO >= ?"
        params.append(data_inicio.isoformat() if hasattr(data_inicio, 'isoformat') else str(data_inicio))

    if data_fim is not None:
        sql += " AND R.DT_VENCTO <= ?"
        params.append(data_fim.isoformat() if hasattr(data_fim, 'isoformat') else str(data_fim))

    if emp_id is not None:
        sql += " AND R.EMP_ID = ?"
        params.append(emp_id)

    sql += " ORDER BY R.DT_VENCTO ASC, R.NUMERO ASC"

    movimentacoes: List[MovimentacaoNormalizada] = []

    with obter_conexao_sisplan() as conn:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        for idx, row in enumerate(rows, start=1):
            (
                r_emp_id,
                r_duplicata,
                r_parcela,
                r_cliente,
                r_classe,
                r_natureza,
                r_dt_pagto,
                r_dt_vencto,
                r_valor_parc,
                r_valor_pago,
                r_val_dev,
                r_status,
                r_banco,
                r_desconto,
            ) = row

            empresa_nome = EMP_ID_MAP.get(r_emp_id, f"EMP_{r_emp_id}")
            doc_str = str(r_duplicata).strip() if r_duplicata else None
            titular_str = str(r_cliente).strip() if r_cliente else "CLIENTE NÃO IDENTIFICADO"
            natureza_str = str(r_natureza).strip() if r_natureza else "RECEITAS GERAIS"

            # Conversão de datas
            dt_transacao = None
            if isinstance(r_dt_pagto, (date, datetime)):
                dt_transacao = r_dt_pagto if isinstance(r_dt_pagto, date) and not isinstance(r_dt_pagto, datetime) else r_dt_pagto.date()

            dt_vencimento = None
            if isinstance(r_dt_vencto, (date, datetime)):
                dt_vencimento = r_dt_vencto if isinstance(r_dt_vencto, date) and not isinstance(r_dt_vencto, datetime) else r_dt_vencto.date()

            # Valores (float)
            val_float = float(r_valor_parc) if isinstance(r_valor_parc, (Decimal, float, int)) else 0.0
            val_pago_float = float(r_valor_pago) if isinstance(r_valor_pago, (Decimal, float, int)) else 0.0
            desc_float = float(r_desconto) if isinstance(r_desconto, (Decimal, float, int)) else 0.0
            total_liquidado = val_pago_float + desc_float
            val_absoluto = abs(val_float)

            # Tratamento de data zero do Delphi (1899-12-30) em DT_PAGTO
            if dt_transacao and is_data_anomala(dt_transacao):
                if total_liquidado >= (val_float - 0.009):
                    dt_transacao = dt_vencimento
                else:
                    dt_transacao = None

            # Para contas a receber, valor é positivo
            valor_final = val_absoluto

            # Aberto se não tem data de pagamento E valor pago/liquidado não atingiu o valor do título
            em_aberto = (dt_transacao is None and total_liquidado < (val_float - 0.009))
            banco_cod = resolver_codigo_banco(r_banco) if r_banco else None

            prefixo, _ = extrair_prefixo_categoria(natureza_str)
            grupo = grupo_categoria(prefixo)
            anomalia = is_data_anomala(dt_vencimento) or (dt_transacao is not None and is_data_anomala(dt_transacao))

            hash_reg = calcular_hash_registro(
                empresa=empresa_nome,
                movimentacao='RECEBER',
                titular=titular_str,
                natureza=natureza_str,
                vencimento=dt_vencimento,
                valor=valor_final,
                banco=banco_cod,
                documento=doc_str,
            )

            mov = MovimentacaoNormalizada(
                linha_excel=idx,
                empresa=empresa_nome,
                movimentacao='RECEBER',
                titular=titular_str,
                natureza=natureza_str,
                prefixo_categoria=prefixo,
                grupo_categoria=grupo,
                data_transacao=dt_transacao,
                vencimento=dt_vencimento,
                valor=valor_final,
                valor_absoluto=val_absoluto,
                em_aberto=em_aberto,
                is_anomalia_data=anomalia,
                hash_registro=hash_reg,
                banco=banco_cod,
                documento=doc_str,
                is_duplicata=False,
            )
            movimentacoes.append(mov)

    return movimentacoes


def extrair_pagar_sisplan(
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    emp_id: Optional[int] = None,
    apenas_ap: bool = True,
) -> List[MovimentacaoNormalizada]:
    """
    Executa a consulta SQL oficial de Contas a Pagar (Tela 130) na base Firebird do Sisplan
    e converte os resultados em objetos MovimentacaoNormalizada prontos para o fluxo de caixa.

    Parâmetros:
        data_inicio: Data mínima de vencimento (DT_VEN).
        data_fim: Data máxima de vencimento (DT_VEN).
        emp_id: Código da empresa (1, 2, 3, 4). Se None, consulta todas as empresas.
        apenas_ap: Se True, filtra por STATUS = 'DUPL' (correspondente a A.P.).
    """
    sql = """
        SELECT 
            P.EMP_ID,
            P.NUM_AP AS NUMERO_AP,
            P.DOCTO AS NOTA_DOC,
            P.DUPLI AS PARCELA,
            P.CODCRE AS COD_FORNECEDOR,
            COALESCE(E.NOME, 'FORNECEDOR NÃO INFORMADO') AS NOME_FORNECEDOR,
            P.NUM_OS AS COD_CLASSE,
            COALESCE(C.DESCRICAO, 'DESPESAS GERAIS') AS NATUREZA,
            (SELECT MAX(P1.DT_LAN) FROM PAGTO1_001 P1 WHERE P1.NUM_AP = P.NUM_AP) AS DATA_PAGAMENTO,
            P.DT_VEN AS DATA_VENCIMENTO,
            COALESCE(P.VALOR, 0) AS VALOR_TITULO,
            COALESCE(P.VAL_PAG, 0) AS VALOR_PAGO,
            P.STATUS,
            P.BANCO,
            COALESCE(CC.DESCRICAO, NULL) AS CENTRO_CUSTO
        FROM PAGTO_001 P
        LEFT JOIN ENTIDADE_001 E ON (P.CODCRE = E.CODCLI)
        LEFT JOIN CLASSE_GER_001 C ON (P.NUM_OS = C.CODIGO)
        LEFT JOIN CENTRO_RATEIO_001 R ON (
            R.ID = (
                SELECT FIRST 1 R2.ID 
                FROM CENTRO_RATEIO_001 R2 
                WHERE R2.EMP_ID = P.EMP_ID AND R2.NUMERO = P.NUM_AP AND R2.TIPO = 'CP'
                ORDER BY R2.PERC_RAT DESC, R2.ID ASC
            )
        )
        LEFT JOIN CENTROCUSTO_001 CC ON (TRIM(COALESCE(R.CENTROCUSTO, P.C_CUSTO)) = TRIM(CC.CODIGO))
        WHERE 1 = 1
    """

    params = []

    if apenas_ap:
        sql += " AND P.STATUS = 'DUPL'"

    if data_inicio is not None:
        sql += " AND P.DT_VEN >= ?"
        params.append(data_inicio.isoformat() if hasattr(data_inicio, 'isoformat') else str(data_inicio))

    if data_fim is not None:
        sql += " AND P.DT_VEN <= ?"
        params.append(data_fim.isoformat() if hasattr(data_fim, 'isoformat') else str(data_fim))

    if emp_id is not None:
        sql += " AND P.EMP_ID = ?"
        params.append(emp_id)

    sql += " ORDER BY P.DT_VEN ASC, P.NUM_AP ASC"

    movimentacoes: List[MovimentacaoNormalizada] = []

    with obter_conexao_sisplan() as conn:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        for idx, row in enumerate(rows, start=1):
            (
                r_emp_id,
                r_num_ap,
                r_docto,
                r_dupli,
                r_codcre,
                r_fornecedor,
                r_classe,
                r_natureza,
                r_dt_pagto,
                r_dt_ven,
                r_valor,
                r_valor_pago,
                r_status,
                r_banco,
                r_centro_custo,
            ) = row

            empresa_nome = EMP_ID_MAP.get(r_emp_id, f"EMP_{r_emp_id}")
            doc_str = str(r_num_ap).strip() if r_num_ap else None
            titular_str = str(r_fornecedor).strip() if r_fornecedor else "FORNECEDOR NÃO INFORMADO"
            natureza_str = str(r_natureza).strip() if r_natureza else "DESPESAS GERAIS"
            cc_str = str(r_centro_custo).strip() if r_centro_custo else None

            # Conversão de datas
            dt_transacao = None
            if isinstance(r_dt_pagto, (date, datetime)):
                dt_transacao = r_dt_pagto if isinstance(r_dt_pagto, date) and not isinstance(r_dt_pagto, datetime) else r_dt_pagto.date()

            dt_vencimento = None
            if isinstance(r_dt_ven, (date, datetime)):
                dt_vencimento = r_dt_ven if isinstance(r_dt_ven, date) and not isinstance(r_dt_ven, datetime) else r_dt_ven.date()

            # Valores (float) - Para PAGAR, valor é negativo no fluxo de caixa
            val_float = float(r_valor) if isinstance(r_valor, (Decimal, float, int)) else 0.0
            val_pago_float = float(r_valor_pago) if isinstance(r_valor_pago, (Decimal, float, int)) else 0.0
            val_absoluto = abs(val_float)
            valor_final = -val_absoluto

            # Tratamento de data zero do Delphi (1899-12-30) em DT_PAGTO
            if dt_transacao and is_data_anomala(dt_transacao):
                if val_pago_float >= (val_float - 0.009):
                    dt_transacao = dt_vencimento
                else:
                    dt_transacao = None

            em_aberto = (dt_transacao is None and val_pago_float < (val_float - 0.009))
            banco_cod = resolver_codigo_banco(r_banco) if r_banco else None

            prefixo, _ = extrair_prefixo_categoria(natureza_str)
            grupo = grupo_categoria(prefixo)
            anomalia = is_data_anomala(dt_vencimento) or (dt_transacao is not None and is_data_anomala(dt_transacao))

            hash_reg = calcular_hash_registro(
                empresa=empresa_nome,
                movimentacao='PAGAR',
                titular=titular_str,
                natureza=natureza_str,
                vencimento=dt_vencimento,
                valor=valor_final,
                banco=banco_cod,
                documento=doc_str,
            )

            mov = MovimentacaoNormalizada(
                linha_excel=idx,
                empresa=empresa_nome,
                movimentacao='PAGAR',
                titular=titular_str,
                natureza=natureza_str,
                prefixo_categoria=prefixo,
                grupo_categoria=grupo,
                data_transacao=dt_transacao,
                vencimento=dt_vencimento,
                valor=valor_final,
                valor_absoluto=val_absoluto,
                em_aberto=em_aberto,
                is_anomalia_data=anomalia,
                hash_registro=hash_reg,
                banco=banco_cod,
                documento=doc_str,
                centro_custo=cc_str,
                is_duplicata=False,
            )
            movimentacoes.append(mov)

    return movimentacoes
