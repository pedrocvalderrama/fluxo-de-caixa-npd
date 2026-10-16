import pandas as pd
from datetime import date
from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from finance_app.database.models import Movimentacao, Empresa, Banco, SaldoDiario
from finance_app.services.filter_service import FiltrosPesquisa, construir_query_movimentacoes
from finance_app.config.empresas import ordem_empresa_chave


def _somar_saldos_filtrados(
    saldos: Dict[Tuple[int, int], float],
    empresas_ids: Optional[List[int]],
    bancos_ids: Optional[List[int]],
) -> float:
    total = 0.0
    for (eid, bid), valor in saldos.items():
        if empresas_ids is not None and eid not in empresas_ids:
            continue
        if bancos_ids is not None and bid not in bancos_ids:
            continue
        total += float(valor or 0.0)
    return total


def calcular_saldo_inicial(
    session: Session, 
    data_inicio: date, 
    empresas_ids: Optional[List[int]] = None,
    bancos_ids: Optional[List[int]] = None,
    usar_saldo_manual: bool = False,
    saldos_iniciais_por_conta: Optional[Dict[Tuple[int, int], float]] = None,
    data_saldo_inicial: Optional[date] = None
) -> float:
    """
    Calcula o saldo inicial antes da data especificada.
    Prioridade:
    1. Se usar_saldo_manual=True e houver valores manuais, usa os saldos manuais informados.
    2. Caso contrário, verifica se existem saldos registrados no banco (SaldoDiario):
       Localiza a data de saldo mais próxima (preferencialmente <= data_inicio) e ajusta pelo delta de movimentações.
    3. Se não houver nenhum SaldoDiario registrado no banco, soma o histórico de movimentações anteriores.
    """
    # 1. Saldo manual explícito
    if usar_saldo_manual and saldos_iniciais_por_conta and data_saldo_inicial is not None:
        saldo_base = _somar_saldos_filtrados(
            saldos_iniciais_por_conta, empresas_ids, bancos_ids
        )
        if data_inicio == data_saldo_inicial:
            return saldo_base
        data_base = data_saldo_inicial
    else:
        # 2. Saldo bancário oficial registrado no banco SQLite (SaldoDiario)
        data_saldo_db = (
            session.query(func.max(SaldoDiario.data))
            .filter(SaldoDiario.data <= data_inicio)
            .scalar()
        )
        if not data_saldo_db:
            data_saldo_db = (
                session.query(func.min(SaldoDiario.data))
                .filter(SaldoDiario.data >= data_inicio)
                .scalar()
            )

        if data_saldo_db is not None:
            query_sd = session.query(SaldoDiario).filter(SaldoDiario.data == data_saldo_db)
            if empresas_ids:
                query_sd = query_sd.filter(SaldoDiario.empresa_id.in_(empresas_ids))
            if bancos_ids:
                query_sd = query_sd.filter(SaldoDiario.banco_id.in_(bancos_ids))
            saldo_base = float(sum(s.saldo for s in query_sd.all()))

            if data_inicio == data_saldo_db:
                return saldo_base
            data_base = data_saldo_db
        else:
            # 3. Fallback: Cálculo antigo (somente se não houver NENHUM SaldoDiario no banco)
            condicoes = [
                Movimentacao.vencimento.is_not(None),
                Movimentacao.vencimento < data_inicio,
                Movimentacao.is_anomalia_data == False,
                Movimentacao.is_duplicata == False
            ]
            if empresas_ids:
                condicoes.append(Movimentacao.empresa_id.in_(empresas_ids))
            if bancos_ids:
                condicoes.append(Movimentacao.banco_id.in_(bancos_ids))
            query = select(func.coalesce(func.sum(Movimentacao.valor), 0.0)).where(and_(*condicoes))
            return float(session.scalar(query) or 0.0)

    # Calcular delta de movimentações entre as duas datas (por vencimento)
    if data_inicio > data_base:
        condicoes = [
            Movimentacao.vencimento.is_not(None),
            Movimentacao.vencimento >= data_base,
            Movimentacao.vencimento < data_inicio,
            Movimentacao.is_anomalia_data == False,
            Movimentacao.is_duplicata == False
        ]
    else:
        condicoes = [
            Movimentacao.vencimento.is_not(None),
            Movimentacao.vencimento >= data_inicio,
            Movimentacao.vencimento < data_base,
            Movimentacao.is_anomalia_data == False,
            Movimentacao.is_duplicata == False
        ]

    if empresas_ids:
        condicoes.append(Movimentacao.empresa_id.in_(empresas_ids))
    if bancos_ids:
        condicoes.append(Movimentacao.banco_id.in_(bancos_ids))

    query = select(func.coalesce(func.sum(Movimentacao.valor), 0.0)).where(and_(*condicoes))
    delta = float(session.scalar(query) or 0.0)

    if data_inicio > data_base:
        return saldo_base + delta
    else:
        return saldo_base - delta

def obter_movimentacoes_simplificadas(session: Session, filtros: FiltrosPesquisa) -> pd.DataFrame:
    """
    Retorna lançamentos filtrados em formato simples:
    Empresa | Banco | vencimento | titular | tipo | valor
    """
    from finance_app.utils.dates import formatar_data

    query = construir_query_movimentacoes(filtros).order_by(
        Movimentacao.vencimento, Movimentacao.id
    )
    movimentacoes = session.scalars(query).all()

    colunas = ['Empresa', 'Banco', 'vencimento', 'titular', 'tipo', 'valor']
    if not movimentacoes:
        return pd.DataFrame(columns=colunas)

    empresas = {e.id: e.nome for e in session.query(Empresa).all()}
    bancos = {b.id: b.nome for b in session.query(Banco).all()}

    linhas = []
    for mov in movimentacoes:
        linhas.append({
            'Empresa': empresas.get(mov.empresa_id, '—'),
            'Banco': bancos.get(mov.banco_id, 'Não informado') if mov.banco_id else 'Não informado',
            'vencimento': formatar_data(mov.vencimento),
            'titular': mov.titular or '',
            'tipo': mov.tipo,
            'valor': float(mov.valor or 0.0),
        })

    return pd.DataFrame(linhas, columns=colunas)


def obter_saidas_do_dia(
    session: Session,
    filtros: FiltrosPesquisa,
    data_ref: date,
) -> pd.DataFrame:
    """
    Lançamentos de saída (PAGAR) de um vencimento específico,
    respeitando os demais filtros da tela.
    """
    from dataclasses import replace

    filtros_dia = replace(
        filtros,
        data_inicio=data_ref,
        data_fim=data_ref,
        tipos=['PAGAR'],
    )
    return obter_movimentacoes_simplificadas(session, filtros_dia)


def obter_fluxo_caixa_diario(session: Session, filtros: FiltrosPesquisa) -> pd.DataFrame:
    """Gera um DataFrame com o fluxo de caixa diário."""
    query = construir_query_movimentacoes(filtros)
    
    movimentacoes = session.scalars(query).all()
    
    dados = []
    for mov in movimentacoes:
        data_ref = mov.vencimento
        if not data_ref:
            continue
            
        dados.append({
            'Data': data_ref,
            'Entradas': mov.valor_absoluto if mov.tipo == 'RECEBER' else 0.0,
            'Saídas': mov.valor if mov.tipo == 'PAGAR' else 0.0,
        })
        
    colunas = [
        'Data', 'Saldo Inicial', 'Entradas', 'Saídas', 'Resultado Diário', 'Saldo Acumulado'
    ]
    df = pd.DataFrame(dados)
    if df.empty:
        return pd.DataFrame(columns=colunas)

    df_agrupado = df.groupby('Data').sum().reset_index()
    df_agrupado['Data'] = pd.to_datetime(df_agrupado['Data']).dt.date
    df_agrupado = df_agrupado.sort_values('Data').reset_index(drop=True)
    df_agrupado['Resultado Diário'] = df_agrupado['Entradas'] + df_agrupado['Saídas']

    if filtros.data_inicio:
        saldo_inicial = calcular_saldo_inicial(
            session,
            filtros.data_inicio,
            filtros.empresas_ids,
            filtros.bancos_ids,
            usar_saldo_manual=filtros.usar_saldo_manual,
            saldos_iniciais_por_conta=filtros.saldos_iniciais_por_conta,
            data_saldo_inicial=filtros.data_saldo_inicial
        )
    else:
        min_data = df_agrupado['Data'].min()
        saldo_inicial = calcular_saldo_inicial(
            session,
            min_data,
            filtros.empresas_ids,
            filtros.bancos_ids,
            usar_saldo_manual=filtros.usar_saldo_manual,
            saldos_iniciais_por_conta=filtros.saldos_iniciais_por_conta,
            data_saldo_inicial=filtros.data_saldo_inicial
        )

    # Saldo de abertura de cada dia = saldo antes das movimentações do dia
    df_agrupado['Saldo Inicial'] = (
        saldo_inicial + df_agrupado['Resultado Diário'].cumsum().shift(1).fillna(0.0)
    )
    df_agrupado['Saldo Acumulado'] = (
        df_agrupado['Saldo Inicial'] + df_agrupado['Resultado Diário']
    )

    return df_agrupado[colunas]


def obter_resumo_por_conta(session: Session, filtros: FiltrosPesquisa) -> pd.DataFrame:
    """
    Consolida visão hierárquica empresa → bancos.

    Sempre lista os 3 bancos oficiais sob cada empresa.
    Inclui Saldo Inicial (quando informado manualmente) e o resultado do período.
    Movimentações sem banco aparecem em "Não informado".

    Colunas: #, Conta, Saldo Inicial, Entradas, Saídas, Resultado
    Resultado = Saldo Inicial + Entradas + Saídas
    """
    from finance_app.config.bancos import BANCOS_PADRAO
    from finance_app.database.repositories.banco_repo import BancoRepository

    BancoRepository(session).seed_padrao()
    session.flush()

    query = construir_query_movimentacoes(filtros)
    movimentacoes = list(session.scalars(query).all())

    colunas = ['#', 'Conta', 'Saldo Inicial', 'Entradas', 'Saídas', 'Resultado']

    empresas_raw = session.query(Empresa).all()
    empresas_q = sorted(empresas_raw, key=ordem_empresa_chave)
    if filtros.empresas_ids is not None:
        empresas_q = [e for e in empresas_q if e.id in filtros.empresas_ids]
    empresas = {e.id: e.nome for e in empresas_q}

    bancos_db = (
        session.query(Banco)
        .filter(Banco.ativo == True)
        .order_by(Banco.codigo)
        .all()
    )
    if filtros.bancos_ids is not None:
        bancos_oficiais = [b for b in bancos_db if b.id in filtros.bancos_ids]
    else:
        # Garante ordem BB → Santander → Sicred
        ordem = {codigo: i for i, (codigo, _) in enumerate(BANCOS_PADRAO)}
        bancos_oficiais = sorted(
            [b for b in bancos_db if b.codigo in ordem],
            key=lambda b: ordem.get(b.codigo, 99),
        )

    # Acumular movimentações por (empresa_id, banco_id|None)
    totais: dict[tuple[int, Optional[int]], dict[str, float]] = {}
    for mov in movimentacoes:
        chave = (mov.empresa_id, mov.banco_id)
        if chave not in totais:
            totais[chave] = {'Entradas': 0.0, 'Saídas': 0.0}
        if mov.tipo == 'RECEBER':
            totais[chave]['Entradas'] += float(mov.valor_absoluto or 0.0)
        else:
            totais[chave]['Saídas'] += float(mov.valor or 0.0)

    saldos = filtros.saldos_iniciais_por_conta or {}
    usar_saldo = bool(filtros.usar_saldo_manual and saldos)
    if not usar_saldo:
        # Busca automaticamente os saldos da data mais adequada registrada em SaldoDiario
        data_saldo_db = None
        if filtros.data_inicio:
            data_saldo_db = (
                session.query(func.max(SaldoDiario.data))
                .filter(SaldoDiario.data <= filtros.data_inicio)
                .scalar()
            )
        if not data_saldo_db:
            data_saldo_db = session.query(func.max(SaldoDiario.data)).scalar()
        if data_saldo_db:
            regs_sd = session.query(SaldoDiario).filter(SaldoDiario.data == data_saldo_db).all()
            if regs_sd:
                saldos = {(r.empresa_id, r.banco_id): r.saldo for r in regs_sd}
                usar_saldo = True

    # Empresas a exibir: com movimento, com saldo informado, ou todas filtradas
    empresas_ids = set(empresas.keys())
    if movimentacoes or usar_saldo:
        ids_mov = {m.empresa_id for m in movimentacoes}
        ids_saldo = {eid for (eid, _) in saldos.keys()} if usar_saldo else set()
        empresas_ids = (ids_mov | ids_saldo) & set(empresas.keys())
        if not empresas_ids and filtros.empresas_ids is None:
            empresas_ids = set(empresas.keys())

    if not empresas_ids and not movimentacoes and not usar_saldo:
        return pd.DataFrame(columns=colunas)

    empresas_ordenadas = sorted(empresas_ids, key=lambda eid: ordem_empresa_chave(empresas.get(eid, '')))

    def _saldo(eid: int, bid: Optional[int]) -> float:
        if not usar_saldo or bid is None:
            return 0.0
        return float(saldos.get((eid, bid), 0.0) or 0.0)

    def _mov(eid: int, bid: Optional[int]) -> tuple[float, float]:
        t = totais.get((eid, bid), {'Entradas': 0.0, 'Saídas': 0.0})
        return float(t['Entradas']), float(t['Saídas'])

    linhas = []
    for idx_emp, empresa_id in enumerate(empresas_ordenadas, start=1):
        nome_empresa = empresas.get(empresa_id, '—')

        # Detalhe dos bancos oficiais (sempre)
        detalhes = []
        for idx_banco, banco in enumerate(bancos_oficiais, start=1):
            ent, sai = _mov(empresa_id, banco.id)
            saldo = _saldo(empresa_id, banco.id)
            detalhes.append({
                '#': f'{idx_emp}.{idx_banco}',
                'Conta': f'    {banco.nome}',
                'Saldo Inicial': saldo,
                'Entradas': ent,
                'Saídas': sai,
                'Resultado': saldo + ent + sai,
            })

        # Movimentações sem banco
        ent_ni, sai_ni = _mov(empresa_id, None)
        if ent_ni != 0.0 or sai_ni != 0.0:
            idx_ni = len(detalhes) + 1
            detalhes.append({
                '#': f'{idx_emp}.{idx_ni}',
                'Conta': '    Não informado',
                'Saldo Inicial': 0.0,
                'Entradas': ent_ni,
                'Saídas': sai_ni,
                'Resultado': ent_ni + sai_ni,
            })

        saldo_emp = sum(d['Saldo Inicial'] for d in detalhes)
        ent_emp = sum(d['Entradas'] for d in detalhes)
        sai_emp = sum(d['Saídas'] for d in detalhes)
        linhas.append({
            '#': str(idx_emp),
            'Conta': nome_empresa,
            'Saldo Inicial': saldo_emp,
            'Entradas': ent_emp,
            'Saídas': sai_emp,
            'Resultado': saldo_emp + ent_emp + sai_emp,
        })
        linhas.extend(detalhes)

    return pd.DataFrame(linhas, columns=colunas)


