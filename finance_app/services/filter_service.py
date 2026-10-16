from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List, Dict, Tuple
from sqlalchemy import select, and_, Select
from finance_app.database.models import Movimentacao, Empresa, Categoria

@dataclass
class FiltrosPesquisa:
    """Filtros para pesquisa de movimentações."""
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    empresas_ids: Optional[List[int]] = None
    bancos_ids: Optional[List[int]] = None
    grupos_categoria: Optional[List[str]] = None
    tipos: Optional[List[str]] = None
    status: str = 'realizado'
    ignorar_anomalias: bool = True
    ignorar_duplicatas: bool = True
    usar_saldo_manual: bool = False
    centros_custo: Optional[List[str]] = None
    # Chave: (empresa_id, banco_id) → saldo informado na data base
    saldos_iniciais_por_conta: Dict[Tuple[int, int], float] = field(default_factory=dict)
    data_saldo_inicial: Optional[date] = None

def construir_query_movimentacoes(filtros: FiltrosPesquisa) -> Select:
    """Constrói a query para buscar movimentações com base nos filtros informados."""
    query = select(Movimentacao)
    
    # Adicionando joins que podem ser úteis para a filtragem
    if filtros.empresas_ids is not None:
        query = query.join(Empresa)
    if filtros.grupos_categoria is not None:
        query = query.join(Categoria)
    
    condicoes = []
    
    if filtros.ignorar_anomalias:
        condicoes.append(Movimentacao.is_anomalia_data == False)
        
    if filtros.ignorar_duplicatas:
        condicoes.append(Movimentacao.is_duplicata == False)
        
    if filtros.empresas_ids:
        condicoes.append(Movimentacao.empresa_id.in_(filtros.empresas_ids))

    if filtros.bancos_ids:
        condicoes.append(Movimentacao.banco_id.in_(filtros.bancos_ids))
        
    if filtros.grupos_categoria:
        condicoes.append(Categoria.grupo.in_(filtros.grupos_categoria))
        
    if filtros.tipos:
        condicoes.append(Movimentacao.tipo.in_(filtros.tipos))

    if filtros.centros_custo:
        condicoes.append(Movimentacao.centro_custo.in_(filtros.centros_custo))
        
    if filtros.status == 'realizado':
        condicoes.append(Movimentacao.data_transacao.is_not(None))
    elif filtros.status == 'projetado':
        condicoes.append(Movimentacao.em_aberto == True)

    # Período sempre filtra pelo vencimento
    if filtros.data_inicio or filtros.data_fim:
        condicoes.append(Movimentacao.vencimento.is_not(None))
        if filtros.data_inicio:
            condicoes.append(Movimentacao.vencimento >= filtros.data_inicio)
        if filtros.data_fim:
            condicoes.append(Movimentacao.vencimento <= filtros.data_fim)
    
    if condicoes:
        query = query.where(and_(*condicoes))
        
    return query
