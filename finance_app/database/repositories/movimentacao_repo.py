"""
Repositório para o modelo Movimentacao.
"""
from datetime import date
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from finance_app.database.models import Movimentacao
from finance_app.database.repositories.base_repository import BaseRepository

class MovimentacaoRepository(BaseRepository[Movimentacao]):
    def __init__(self, session: Session):
        super().__init__(Movimentacao, session)

    def get_por_periodo(self, data_inicio: date, data_fim: date) -> List[Movimentacao]:
        """Retorna as movimentações ocorridas em um determinado período."""
        stmt = select(Movimentacao).where(
            Movimentacao.data_transacao >= data_inicio,
            Movimentacao.data_transacao <= data_fim
        )
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def get_por_tipo(self, tipo: str) -> List[Movimentacao]:
        """Retorna as movimentações de um determinado tipo (PAGAR ou RECEBER)."""
        stmt = select(Movimentacao).where(Movimentacao.tipo == tipo)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def get_por_empresa(self, empresa_id: int) -> List[Movimentacao]:
        """Retorna as movimentações vinculadas a uma empresa específica."""
        stmt = select(Movimentacao).where(Movimentacao.empresa_id == empresa_id)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def get_por_categoria(self, categoria_id: int) -> List[Movimentacao]:
        """Retorna as movimentações vinculadas a uma categoria específica."""
        stmt = select(Movimentacao).where(Movimentacao.categoria_id == categoria_id)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def total_entradas(self, data_inicio: Optional[date] = None, data_fim: Optional[date] = None) -> float:
        """Calcula o valor total de entradas (RECEBER)."""
        stmt = select(func.sum(Movimentacao.valor)).where(Movimentacao.tipo == 'RECEBER')
        if data_inicio:
            stmt = stmt.where(Movimentacao.data_transacao >= data_inicio)
        if data_fim:
            stmt = stmt.where(Movimentacao.data_transacao <= data_fim)
            
        result = self.session.execute(stmt)
        total = result.scalar_one_or_none()
        return float(total) if total else 0.0

    def total_saidas(self, data_inicio: Optional[date] = None, data_fim: Optional[date] = None) -> float:
        """Calcula o valor total de saídas (PAGAR)."""
        stmt = select(func.sum(Movimentacao.valor)).where(Movimentacao.tipo == 'PAGAR')
        if data_inicio:
            stmt = stmt.where(Movimentacao.data_transacao >= data_inicio)
        if data_fim:
            stmt = stmt.where(Movimentacao.data_transacao <= data_fim)
            
        result = self.session.execute(stmt)
        total = result.scalar_one_or_none()
        return float(total) if total else 0.0

    def count_por_importacao(self, importacao_id: int) -> int:
        """Conta quantas movimentações existem para uma importação."""
        stmt = select(func.count()).select_from(Movimentacao).where(Movimentacao.importacao_id == importacao_id)
        result = self.session.execute(stmt)
        return result.scalar_one()

    def get_duplicatas(self) -> List[Movimentacao]:
        """Retorna as movimentações marcadas como duplicadas."""
        stmt = select(Movimentacao).where(Movimentacao.is_duplicata == True)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def get_em_aberto(self) -> List[Movimentacao]:
        """Retorna as movimentações em aberto (sem data de transação/pagamento)."""
        stmt = select(Movimentacao).where(Movimentacao.em_aberto == True)
        result = self.session.execute(stmt)
        return list(result.scalars().all())
