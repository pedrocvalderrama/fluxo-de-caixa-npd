"""
Repositório para o modelo Importacao.
"""
from typing import Optional, List
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from finance_app.database.models import Importacao
from finance_app.database.repositories.base_repository import BaseRepository

class ImportacaoRepository(BaseRepository[Importacao]):
    def __init__(self, session: Session):
        super().__init__(Importacao, session)

    def get_by_hash(self, hash_arquivo: str) -> Optional[Importacao]:
        """Busca uma importação pelo hash do arquivo."""
        stmt = select(Importacao).where(Importacao.hash_arquivo == hash_arquivo)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def hash_exists(self, hash_arquivo: str) -> bool:
        """Verifica se um hash de arquivo já existe no banco."""
        return self.get_by_hash(hash_arquivo) is not None

    def get_recentes(self, limit: int = 10) -> List[Importacao]:
        """Retorna as importações mais recentes."""
        stmt = select(Importacao).order_by(desc(Importacao.data_importacao)).limit(limit)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def atualizar_status(self, id: int, status: str, observacoes: Optional[str] = None) -> Optional[Importacao]:
        """Atualiza o status e as observações de uma importação."""
        importacao = self.get_by_id(id)
        if importacao:
            importacao.status = status
            if observacoes is not None:
                importacao.observacoes = observacoes
            self.session.flush()
        return importacao
