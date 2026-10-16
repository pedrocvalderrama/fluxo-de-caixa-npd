"""
Serviço para listar anomalias de data e duplicatas persistidas.
"""
from typing import Optional
from collections import defaultdict
import pandas as pd
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from finance_app.database.models import Movimentacao, Empresa, Banco, Categoria
from finance_app.services.filter_service import FiltrosPesquisa
from finance_app.utils.dates import formatar_data


MOTIVO_DUPLICATA = (
    "Mesmo hash: empresa + banco + tipo + titular + natureza + vencimento + valor + documento"
)


def _aplicar_filtros_base(filtros: FiltrosPesquisa, *extras):
    """Filtros de período/empresa/banco/status sem excluir anomalias ou duplicatas."""
    condicoes = list(extras)

    if filtros.empresas_ids:
        condicoes.append(Movimentacao.empresa_id.in_(filtros.empresas_ids))
    if filtros.bancos_ids:
        condicoes.append(Movimentacao.banco_id.in_(filtros.bancos_ids))
    if filtros.tipos:
        condicoes.append(Movimentacao.tipo.in_(filtros.tipos))

    if filtros.status == "realizado":
        condicoes.append(Movimentacao.data_transacao.is_not(None))
    elif filtros.status == "projetado":
        condicoes.append(Movimentacao.em_aberto == True)

    if filtros.data_inicio or filtros.data_fim:
        condicoes.append(Movimentacao.vencimento.is_not(None))
        if filtros.data_inicio:
            condicoes.append(Movimentacao.vencimento >= filtros.data_inicio)
        if filtros.data_fim:
            condicoes.append(Movimentacao.vencimento <= filtros.data_fim)

    return and_(*condicoes) if condicoes else None


def _mapas(session: Session) -> tuple[dict, dict, dict]:
    empresas = {e.id: e.nome for e in session.query(Empresa).all()}
    bancos = {b.id: b.nome for b in session.query(Banco).all()}
    categorias = {c.id: c.nome for c in session.query(Categoria).all()}
    return empresas, bancos, categorias


def obter_anomalias(session: Session, filtros: Optional[FiltrosPesquisa] = None) -> pd.DataFrame:
    """Retorna lançamentos marcados com is_anomalia_data=True."""
    filtros = filtros or FiltrosPesquisa(status="todos")
    where = _aplicar_filtros_base(filtros, Movimentacao.is_anomalia_data == True)
    stmt = select(Movimentacao).where(where).order_by(Movimentacao.vencimento, Movimentacao.id)
    movs = list(session.scalars(stmt).all())

    colunas = [
        "Empresa", "Banco", "vencimento", "data_transacao",
        "titular", "tipo", "valor", "motivo",
    ]
    if not movs:
        return pd.DataFrame(columns=colunas)

    empresas, bancos, _ = _mapas(session)
    linhas = []
    for mov in movs:
        linhas.append({
            "Empresa": empresas.get(mov.empresa_id, "—"),
            "Banco": bancos.get(mov.banco_id, "Não informado") if mov.banco_id else "Não informado",
            "vencimento": formatar_data(mov.vencimento),
            "data_transacao": formatar_data(mov.data_transacao),
            "titular": mov.titular or "",
            "tipo": mov.tipo,
            "valor": float(mov.valor or 0.0),
            "motivo": "Data anômala (antes de 1950 ou após 2050)",
        })
    return pd.DataFrame(linhas, columns=colunas)


def obter_duplicatas(session: Session, filtros: Optional[FiltrosPesquisa] = None) -> pd.DataFrame:
    """
    Retorna TODOS os lançamentos de cada grupo duplicado.

    1) Usa os filtros da tela para achar lançamentos cujo hash aparece 2+ vezes no banco.
    2) Para esses hashes, traz o grupo completo (todas as ocorrências), mesmo que
       alguma fique fora do período de vencimento filtrado.
    """
    filtros = filtros or FiltrosPesquisa(status="todos")
    colunas_vazias = [
        "Grupo", "Ocorrência", "Empresa", "Banco", "vencimento", "data_transacao",
        "titular", "natureza", "tipo", "valor", "marcado_duplicata", "motivo",
    ]

    # Hashes com 2+ ocorrências no banco inteiro
    stmt_hashes = (
        select(Movimentacao.hash_registro)
        .where(
            Movimentacao.hash_registro.is_not(None),
            Movimentacao.hash_registro != "",
        )
        .group_by(Movimentacao.hash_registro)
        .having(func.count(Movimentacao.id) > 1)
    )
    hashes_dup = {h for h in session.scalars(stmt_hashes).all() if h}
    if not hashes_dup:
        return pd.DataFrame(columns=colunas_vazias)

    # Quais desses hashes têm pelo menos 1 lançamento dentro do filtro da tela
    where_filtrado = _aplicar_filtros_base(
        filtros,
        Movimentacao.hash_registro.in_(hashes_dup),
    )
    hashes_no_periodo = set(
        session.scalars(
            select(Movimentacao.hash_registro).where(where_filtrado).distinct()
        ).all()
    )
    hashes_no_periodo = {h for h in hashes_no_periodo if h}
    if not hashes_no_periodo:
        return pd.DataFrame(columns=colunas_vazias)

    # Grupo completo de cada hash (sem filtro de vencimento)
    stmt_grupo = (
        select(Movimentacao)
        .where(Movimentacao.hash_registro.in_(hashes_no_periodo))
        .order_by(Movimentacao.hash_registro, Movimentacao.id)
    )
    movs = list(session.scalars(stmt_grupo).all())
    if not movs:
        return pd.DataFrame(columns=colunas_vazias)

    empresas, bancos, categorias = _mapas(session)
    por_hash: dict[str, list] = defaultdict(list)
    for mov in movs:
        por_hash[mov.hash_registro].append(mov)

    linhas = []
    grupo_n = 0
    for _, grupo in por_hash.items():
        if len(grupo) < 2:
            continue
        grupo_n += 1
        total = len(grupo)
        for idx, mov in enumerate(grupo, start=1):
            linhas.append({
                "Grupo": grupo_n,
                "Ocorrência": f"{idx}/{total}",
                "Empresa": empresas.get(mov.empresa_id, "—"),
                "Banco": bancos.get(mov.banco_id, "Não informado") if mov.banco_id else "Não informado",
                "vencimento": formatar_data(mov.vencimento),
                "data_transacao": formatar_data(mov.data_transacao),
                "titular": mov.titular or "",
                "natureza": categorias.get(mov.categoria_id, "") if mov.categoria_id else "",
                "tipo": mov.tipo,
                "valor": float(mov.valor or 0.0),
                "marcado_duplicata": "Sim" if mov.is_duplicata else "Não (1º do grupo)",
                "motivo": MOTIVO_DUPLICATA,
            })

    return pd.DataFrame(linhas)
