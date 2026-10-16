"""
Repositório para o modelo Banco.
"""
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_app.database.models import Banco
from finance_app.database.repositories.base_repository import BaseRepository
from finance_app.config.bancos import BANCOS_PADRAO


class BancoRepository(BaseRepository[Banco]):
    def __init__(self, session: Session):
        super().__init__(Banco, session)

    def get_by_codigo(self, codigo: str) -> Optional[Banco]:
        stmt = select(Banco).where(Banco.codigo == codigo)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def get_by_nome(self, nome: str) -> Optional[Banco]:
        stmt = select(Banco).where(Banco.nome == nome)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def get_or_create(self, codigo: str, nome: str) -> Banco:
        banco = self.get_by_codigo(codigo)
        if not banco:
            banco = Banco(codigo=codigo, nome=nome)
            self.create(banco)
        return banco

    def get_ativos(self) -> List[Banco]:
        stmt = select(Banco).where(Banco.ativo == True).order_by(Banco.codigo)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def seed_padrao(self) -> List[Banco]:
        """Garante que os 3 bancos oficiais existam."""
        bancos = []
        for codigo, nome in BANCOS_PADRAO:
            bancos.append(self.get_or_create(codigo, nome))
        return bancos
