"""
Repositório para o modelo Empresa.
"""
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_app.database.models import Empresa
from finance_app.database.repositories.base_repository import BaseRepository

class EmpresaRepository(BaseRepository[Empresa]):
    def __init__(self, session: Session):
        super().__init__(Empresa, session)

    def get_by_codigo(self, codigo: str) -> Optional[Empresa]:
        """Busca uma empresa pelo código original."""
        stmt = select(Empresa).where(Empresa.codigo == codigo)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def get_by_nome(self, nome: str) -> Optional[Empresa]:
        """Busca uma empresa pelo nome mapeado."""
        stmt = select(Empresa).where(Empresa.nome == nome)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def get_or_create(self, codigo: str, nome: str) -> Empresa:
        """Obtém uma empresa existente pelo código ou cria uma nova se não existir."""
        empresa = self.get_by_codigo(codigo)
        if not empresa:
            empresa = Empresa(codigo=codigo, nome=nome)
            self.create(empresa)
        return empresa

    def get_ativas(self) -> List[Empresa]:
        """Retorna todas as empresas ativas."""
        stmt = select(Empresa).where(Empresa.ativa == True)
        result = self.session.execute(stmt)
        return list(result.scalars().all())
