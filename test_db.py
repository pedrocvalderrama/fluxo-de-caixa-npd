import sys
import os

project_dir = r'c:\dev\FLUXO DE CAIXA'
sys.path.insert(0, project_dir)

try:
    from finance_app.database.connection import engine, SessionLocal, Base, init_db, get_session
    from finance_app.database.models import Empresa, Categoria, Importacao, MovimentacaoRaw, Movimentacao
    from finance_app.database.repositories.base_repository import BaseRepository
    from finance_app.database.repositories.empresa_repo import EmpresaRepository
    from finance_app.database.repositories.categoria_repo import CategoriaRepository
    from finance_app.database.repositories.importacao_repo import ImportacaoRepository
    from finance_app.database.repositories.movimentacao_repo import MovimentacaoRepository

    print('All models and repositories imported successfully')
    
    init_db()
    print('Tables:', [t.name for t in Base.metadata.sorted_tables])
except Exception as e:
    import traceback
    traceback.print_exc()
