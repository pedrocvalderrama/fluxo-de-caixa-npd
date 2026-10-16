"""
Repositório base com operações CRUD genéricas.
"""
from typing import Generic, TypeVar, Type, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func

T = TypeVar('T')

class BaseRepository(Generic[T]):
    """Classe base para repositórios."""
    
    def __init__(self, model_class: Type[T], session: Session):
        self.model_class = model_class
        self.session = session

    def get_by_id(self, id: int) -> Optional[T]:
        """Obtém um registro pelo ID."""
        return self.session.get(self.model_class, id)

    def get_all(self) -> List[T]:
        """Obtém todos os registros da tabela."""
        stmt = select(self.model_class)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def create(self, obj: T) -> T:
        """Cria e persiste um novo registro."""
        self.session.add(obj)
        self.session.flush()
        return obj

    def create_many(self, objs: List[T]) -> List[T]:
        """Cria múltiplos registros de uma vez."""
        self.session.add_all(objs)
        self.session.flush()
        return objs

    def update(self, obj: T) -> T:
        """Atualiza um registro existente."""
        self.session.merge(obj)
        self.session.flush()
        return obj

    def delete(self, id: int) -> bool:
        """Remove um registro pelo ID."""
        obj = self.get_by_id(id)
        if obj:
            self.session.delete(obj)
            self.session.flush()
            return True
        return False

    def count(self) -> int:
        """Retorna o número total de registros."""
        stmt = select(func.count()).select_from(self.model_class)
        result = self.session.execute(stmt)
        return result.scalar_one()

    def exists(self, id: int) -> bool:
        """Verifica se um registro existe pelo ID."""
        return self.get_by_id(id) is not None
