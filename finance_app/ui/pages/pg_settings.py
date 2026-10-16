"""
Página de Configurações e Manutenção.
"""
import streamlit as st
import shutil
from pathlib import Path
from datetime import datetime
import pandas as pd

from finance_app.database.connection import engine, init_db, get_session, reset_db
from finance_app.config.settings import settings
from finance_app.database.repositories.importacao_repo import ImportacaoRepository

def renderizar_pagina():
    """Renderiza a aba de configurações."""
    st.markdown("## ⚙️ Configurações do Sistema")
    st.markdown("Gerencie dados locais, logs e preferências.")
    st.divider()

    db_path_str = settings.DATABASE_URL.replace('sqlite:///', '')
    db_path = Path(db_path_str)

    settings.ensure_dirs()

    # --- Seção 1: Backup do Banco de Dados ---
    st.markdown("### 📦 Backup do Banco de Dados")
    st.info(f"O banco de dados SQLite está operando normalmente em: `{db_path}`")
    
    if st.button("Criar Backup", type="primary"):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'finance_{timestamp}.db'
        backup_path = settings.BACKUP_DIR / backup_filename
        try:
            shutil.copy2(str(db_path), str(backup_path))
            st.success(f"Backup criado com sucesso em: {backup_path}")
            
            with open(backup_path, "rb") as f:
                st.download_button(
                    label="📥 Baixar Backup Criado",
                    data=f,
                    file_name=backup_filename,
                    mime="application/octet-stream"
                )
        except Exception as e:
            st.error(f"Erro ao criar backup: {e}")

    st.markdown("#### Backups Existentes")
    backups = list(settings.BACKUP_DIR.glob("*.db"))
    if backups:
        dados_backups = []
        for b in backups:
            stats = b.stat()
            tamanho_mb = stats.st_size / (1024 * 1024)
            data_mod = datetime.fromtimestamp(stats.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
            dados_backups.append({"Arquivo": b.name, "Data": data_mod, "Tamanho (MB)": f"{tamanho_mb:.2f}"})
        st.dataframe(pd.DataFrame(dados_backups), hide_index=True)
    else:
        st.info("Nenhum backup encontrado.")

    st.divider()

    # --- Seção 2: Restaurar Backup ---
    st.markdown("### 📥 Restaurar Backup")
    uploaded_file = st.file_uploader("Selecione um arquivo de backup (.db)", type=["db"])
    if uploaded_file is not None:
        st.warning("⚠️ A restauração irá substituir o banco de dados atual. O sistema pode precisar ser reiniciado.")
        confirm_restore = st.checkbox("Eu entendo e quero prosseguir com a restauração.")
        if st.button("Restaurar", type="primary", disabled=not confirm_restore):
            try:
                # Fecha conexões
                engine.dispose()
                
                # Salva o arquivo enviado por cima do atual
                with open(db_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                init_db()
                st.success("Restauração concluída com sucesso! Recarregue a página.")
                st.balloons()
            except Exception as e:
                st.error(f"Erro ao restaurar banco de dados: {e}")

    st.divider()

    # --- Seção 3: Histórico de Importações ---
    st.markdown("### 📋 Histórico de Importações")
    try:
        with get_session() as session:
            repo = ImportacaoRepository(session)
            recentes = repo.get_recentes(limit=20)
            
            if recentes:
                dados_imp = []
                for imp in recentes:
                    dados_imp.append({
                        "Arquivo": imp.arquivo,
                        "Data": imp.data_importacao.strftime("%d/%m/%Y %H:%M") if imp.data_importacao else "",
                        "Registros": imp.qtd_registros,
                        "Erros": imp.qtd_erros,
                        "Status": imp.status
                    })
                st.dataframe(pd.DataFrame(dados_imp), hide_index=True)
            else:
                st.info("Nenhuma importação encontrada.")
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")

    st.divider()

    # --- Seção 4: Zona de Perigo ---
    with st.expander("⚠️ Zona de Perigo (Zerar Sistema)", expanded=False):
        st.warning("A ação abaixo irá deletar todas as movimentações, empresas, categorias e histórico de importações do sistema de forma irreversível.")
        
        confirm = st.checkbox("Eu entendo que os dados serão apagados permanentemente.")
        if st.button("🗑️ Resetar Banco de Dados", type="primary", disabled=not confirm):
            try:
                reset_db()
                st.success("Banco de dados resetado com sucesso!")
                st.balloons()
            except Exception as e:
                st.error(f"Não foi possível resetar o banco de dados. Erro: {e}")

    st.divider()

    # --- Seção 5: Informações do Sistema ---
    st.markdown("### 🖥️ Informações do Sistema")
    st.markdown(f"- **Versão do App:** {settings.APP_VERSION}")
    st.markdown(f"- **Diretório de Dados:** `{settings.BASE_DIR / 'data'}`")
    st.markdown(f"- **Máximo de Linhas no Preview de Importação:** {settings.MAX_PREVIEW_ROWS}")

if __name__ == "__main__":
    renderizar_pagina()
