"""
Repositório para o modelo Categoria.
"""
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_app.database.models import Categoria
from finance_app.database.repositories.base_repository import BaseRepository

class CategoriaRepository(BaseRepository[Categoria]):
    def __init__(self, session: Session):
        super().__init__(Categoria, session)

    def get_by_nome(self, nome: str) -> Optional[Categoria]:
        """Busca uma categoria pelo nome completo normalizado."""
        stmt = select(Categoria).where(Categoria.nome == nome)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def get_or_create(self, nome: str, codigo: Optional[str] = None, grupo: Optional[str] = None) -> Categoria:
        """Obtém uma categoria pelo nome ou a cria."""
        categoria = self.get_by_nome(nome)
        if not categoria:
            categoria = Categoria(nome=nome, codigo=codigo, grupo=grupo)
            self.create(categoria)
        return categoria

    def get_ativas(self) -> List[Categoria]:
        """Retorna todas as categorias ativas."""
        stmt = select(Categoria).where(Categoria.ativa == True)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def get_by_grupo(self, grupo: str) -> List[Categoria]:
        """Retorna todas as categorias pertencentes a um determinado grupo."""
        stmt = select(Categoria).where(Categoria.grupo == grupo)
        result = self.session.execute(stmt)
        return list(result.scalars().all())
