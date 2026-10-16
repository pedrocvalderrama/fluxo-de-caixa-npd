"""
Orquestrador do fluxo completo de importação do Excel para o banco de dados.
"""
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Any
from sqlalchemy.orm import Session
from datetime import datetime

from finance_app.ingestion.excel_reader import ler_excel
from finance_app.ingestion.validator import validar_dataframe
from finance_app.ingestion.normalizer import normalizar_dataframe, MovimentacaoNormalizada
from finance_app.ingestion.duplicate_detector import (
    processar_analise_importacao,
    ResultadoAnaliseImportacao,
)

from finance_app.database.models import Importacao, MovimentacaoRaw, Movimentacao
from finance_app.database.repositories.empresa_repo import EmpresaRepository
from finance_app.database.repositories.banco_repo import BancoRepository
from finance_app.database.repositories.categoria_repo import CategoriaRepository
from finance_app.database.repositories.importacao_repo import ImportacaoRepository


def criar_backup_automatico() -> Optional[str]:
    """Cria backup automático do banco antes de uma importação.
    Retorna o caminho do backup ou None se falhar."""
    from finance_app.config.settings import settings
    import shutil
    from datetime import datetime

    db_path_str = settings.DATABASE_URL.replace('sqlite:///', '')
    db_path = Path(db_path_str)

    if not db_path.exists():
        return None

    settings.ensure_dirs()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = settings.BACKUP_DIR / f'finance_auto_{timestamp}.db'

    try:
        shutil.copy2(str(db_path), str(backup_path))
        return str(backup_path)
    except Exception:
        return None


# Mapeamento inverso: nome da empresa → código original
EMP_MAP_INVERSO = {
    'NPD': '_001',
    'COMPRE': '_002',
    'DEMO': '_003',
    'CS': '_004',
}

BATCH_SIZE = 1000


@dataclass
class ProgressoImportacao:
    etapa: str
    progresso: float  # 0.0 a 1.0
    mensagem: str
    concluida: bool = False
    erro: Optional[str] = None


@dataclass
class ResultadoImportacao:
    sucesso: bool
    importacao_id: Optional[int]
    arquivo: str
    total_lidos: int
    total_importados: int
    total_atualizados: int          # Existentes cujos valores, vencimentos ou pagamentos foram atualizados (UPDATE)
    total_erros: int
    total_duplicatas: int           # Duplicatas internas inseridas e sinalizadas
    total_ja_existentes: int        # Ignoradas por já existirem e estarem inalteradas
    total_em_aberto: int
    mensagem: str
    detalhes: list[str] = field(default_factory=list)


def verificar_hash_duplicado(hash_arquivo: str, session: Session) -> bool:
    """Verifica se já existe importação com este hash no banco."""
    repo = ImportacaoRepository(session)
    return repo.hash_exists(hash_arquivo)


def carregar_banco_para_conciliacao(session: Session) -> tuple[dict[str, Movimentacao], dict[tuple, Movimentacao]]:
    """
    Carrega do banco de dados:
    1. mapa_hashes: dicionário com hash_registro -> Movimentacao.
    2. mapa_negocio_banco: dicionário com chaves (empresa, tipo, doc_clean, natureza_clean) e (tipo, doc_clean, natureza_clean) -> Movimentacao
    """
    from sqlalchemy import select
    from finance_app.database.models import Categoria, Empresa

    stmt = select(Movimentacao, Categoria.nome.label('cat_nome'), Empresa.nome.label('emp_nome')).outerjoin(
        Categoria, Movimentacao.categoria_id == Categoria.id
    ).outerjoin(
        Empresa, Movimentacao.empresa_id == Empresa.id
    )
    rows = session.execute(stmt).all()

    mapa_hashes: dict[str, Movimentacao] = {}
    mapa_negocio: dict[tuple, Movimentacao] = {}

    for mov, cat_nome, emp_nome in rows:
        mov._categoria_nome = cat_nome or ''
        mov._empresa_nome = emp_nome or ''
        if mov.hash_registro:
            mapa_hashes[mov.hash_registro] = mov

        doc_clean = mov.documento.strip().lstrip('0') if mov.documento else ''
        nat_clean = (cat_nome or '').strip().upper()
        emp_clean = (emp_nome or '').strip().upper()

        if doc_clean:
            chave_emp_doc = (emp_clean, mov.tipo, doc_clean)
            chave_tipo_doc = (mov.tipo, doc_clean)
            chave_completa = (emp_clean, mov.tipo, doc_clean, nat_clean)
            chave_legado = (mov.tipo, doc_clean, nat_clean)
            mapa_negocio[chave_emp_doc] = mov
            mapa_negocio[chave_tipo_doc] = mov
            mapa_negocio[chave_completa] = mov
            mapa_negocio[chave_legado] = mov

    return mapa_hashes, mapa_negocio


def hashes_existentes_no_banco(session: Session) -> set[str]:
    """Retorna o conjunto de hash_registro já persistidos."""
    mapa_hashes, _ = carregar_banco_para_conciliacao(session)
    return set(mapa_hashes.keys())


def importar_excel(
    caminho_arquivo: str | Path,
    session: Session,
    callback_progresso: Optional[Callable[[ProgressoImportacao], Any]] = None,
) -> ResultadoImportacao:
    """
    Executa o fluxo completo de importação de um arquivo Excel para o banco de dados.

    Etapas:
        1. Ler Excel
        2. Verificar duplicidade de arquivo (hash)
        3. Validar dados
        4. Normalizar dados
        5. Conciliar com o banco por (Tipo, Numero/Duplicata, Natureza): inalterados (ignorar), atualizações (UPDATE) e novos (INSERT)
        6. Criar registro de Importacao no banco
        7. Atualizar registros existentes que sofreram alteração no Vencimento, Valor ou Data de Transação (UPDATE)
        8. Inserir dados brutos (MovimentacaoRaw) e normalizados (Movimentacao) dos registros novos (INSERT)
        9. Atualizar status para CONCLUIDA
    """
    inicio = time.time()

    def _progresso(etapa: str, prog: float, msg: str, concluida: bool = False, erro: str = None):
        if callback_progresso:
            callback_progresso(
                ProgressoImportacao(
                    etapa=etapa,
                    progresso=prog,
                    mensagem=msg,
                    concluida=concluida,
                    erro=erro,
                )
            )

    arquivo_path = Path(caminho_arquivo)

    try:
        # ── Auto-backup ──────────────────────────────────────────────────────
        _progresso("Backup automático", 0.05, "Criando backup de segurança...")
        criar_backup_automatico()

        # ── Etapa 1: Ler Excel (10%) ────────────────────────────────────────
        _progresso("Lendo Excel", 0.10, f"Lendo {arquivo_path.name}...")
        resultado_leitura = ler_excel(arquivo_path)
        df_mapped = resultado_leitura.df_mapped
        if df_mapped.empty:
            raise ValueError("O arquivo Excel está vazio ou não pôde ser lido.")

        # ── Etapa 2: Verificar hash duplicado de arquivo (20%) ──────────────
        _progresso("Verificando arquivo", 0.20, "Verificando se a planilha já foi importada...")
        hash_arquivo = resultado_leitura.hash_arquivo
        if verificar_hash_duplicado(hash_arquivo, session):
            raise ValueError(
                f"O arquivo '{arquivo_path.name}' já foi importado anteriormente. "
                "Remova-o do histórico antes de reimportar."
            )

        # ── Etapa 3: Validar dados (30%) ────────────────────────────────────
        _progresso("Validando dados", 0.30, "Verificando inconsistências nos dados...")
        resultado_validacao = validar_dataframe(df_mapped)

        # ── Etapa 4: Normalizar dados (40%) ─────────────────────────────────
        _progresso("Normalizando dados", 0.40, "Formatando valores e datas...")
        movimentacoes_norm, erros_norm = normalizar_dataframe(df_mapped)

        # ── Etapa 5: Conciliar com banco SQL por (Tipo, Doc, Natureza) (55%) ─
        _progresso("Conciliando dados", 0.55, "Comparando registros com o banco SQL por Documento e Natureza...")
        hashes_banco, mapa_negocio_banco = carregar_banco_para_conciliacao(session)
        analise = processar_analise_importacao(movimentacoes_norm, hashes_banco, mapa_negocio_banco)

        movs_para_inserir = analise.novos_para_inserir
        atualizacoes = analise.atualizacoes
        total_ja_existentes = analise.ja_existentes_count
        total_duplicatas_internas = analise.duplicatas_internas_count

        if not movs_para_inserir and not atualizacoes:
            _progresso("Concluído", 1.0, "Todos os registros da planilha já existem no banco SQL.", concluida=True)
            return ResultadoImportacao(
                sucesso=True,
                importacao_id=None,
                arquivo=arquivo_path.name,
                total_lidos=len(movimentacoes_norm),
                total_importados=0,
                total_atualizados=0,
                total_erros=len(erros_norm),
                total_duplicatas=0,
                total_ja_existentes=total_ja_existentes,
                total_em_aberto=0,
                mensagem=f"Todos os {total_ja_existentes:,} registros da planilha já existem no banco de dados sem alterações.",
                detalhes=["Nenhum registro novo ou alterado para importar."],
            )

        # ── Etapa 6: Registrar importação no banco (65%) ────────────────────
        _progresso("Registrando importação", 0.65, "Iniciando transação no banco de dados...")
        importacao = Importacao(
            arquivo=arquivo_path.name,
            hash_arquivo=hash_arquivo,
            data_importacao=datetime.now(),
            qtd_registros=len(movs_para_inserir) + len(atualizacoes),
            qtd_erros=len(erros_norm),
            qtd_duplicados=total_duplicatas_internas,
            status="PENDENTE",
            observacoes=(
                f"Importação iniciada. {len(movs_para_inserir)} novos, "
                f"{len(atualizacoes)} atualizados, {total_ja_existentes} inalterados."
            ),
        )
        session.add(importacao)
        session.flush()

        # ── Etapa 7: Executar ATUALIZAÇÕES (UPDATE) no banco SQL (75%) ───────
        if atualizacoes:
            _progresso("Atualizando registros", 0.75, f"Atualizando {len(atualizacoes):,} registros existentes (vencimento/valor/pagto)...")
            repo_cat_upd = CategoriaRepository(session)
            repo_bco_upd = BancoRepository(session)
            for item in atualizacoes:
                mov_bd = item.mov_banco
                m_norm = item.mov_norm

                mov_bd.vencimento = m_norm.vencimento
                mov_bd.valor = m_norm.valor
                mov_bd.valor_absoluto = m_norm.valor_absoluto
                mov_bd.data_transacao = m_norm.data_transacao
                mov_bd.em_aberto = m_norm.em_aberto
                mov_bd.titular = m_norm.titular
                mov_bd.hash_registro = m_norm.hash_registro
                mov_bd.is_anomalia_data = m_norm.is_anomalia_data
                mov_bd.centro_custo = m_norm.centro_custo
                mov_bd.importacao_id = importacao.id

                if m_norm.natureza:
                    cat_obj = repo_cat_upd.get_or_create(
                        nome=m_norm.natureza,
                        codigo=m_norm.prefixo_categoria,
                        grupo=m_norm.grupo_categoria,
                    )
                    mov_bd.categoria_id = cat_obj.id

                if m_norm.banco:
                    bco_obj = repo_bco_upd.get_by_codigo(m_norm.banco)
                    if bco_obj:
                        mov_bd.banco_id = bco_obj.id
            session.flush()

        # ── Etapa 8: Salvar dados brutos (MovimentacaoRaw) e novos (INSERT) (90%) ──
        total_em_aberto = sum(1 for m in movs_para_inserir if m.em_aberto)

        if movs_para_inserir:
            _progresso("Salvando novos registros", 0.85, f"Persistindo {len(movs_para_inserir):,} registros novos...")
            linhas_novas_set = set(m.linha_excel for m in movs_para_inserir)
            batch_raw: list[MovimentacaoRaw] = []

            for idx, row in enumerate(df_mapped.itertuples(index=False)):
                linha_excel = getattr(row, 'linha_excel', idx + 2)
                if linha_excel not in linhas_novas_set:
                    continue

                mov_raw = MovimentacaoRaw(
                    importacao_id=importacao.id,
                    empresa_original=str(getattr(row, 'empresa', '') or ''),
                    banco_original=str(getattr(row, 'banco', '') or ''),
                    movimentacao_original=str(getattr(row, 'movimentacao', '') or ''),
                    titular_original=str(getattr(row, 'titular', '') or ''),
                    natureza_original=str(getattr(row, 'natureza', '') or ''),
                    data_transacao_original=str(getattr(row, 'data_transacao', '') or ''),
                    vencimento_original=str(getattr(row, 'vencimento', '') or ''),
                    valor_original=str(getattr(row, 'valor', '') or ''),
                    documento_original=str(getattr(row, 'documento', '') or '') or None,
                    linha_excel=linha_excel,
                )
                batch_raw.append(mov_raw)

                if len(batch_raw) >= BATCH_SIZE:
                    session.bulk_save_objects(batch_raw)
                    batch_raw.clear()

            if batch_raw:
                session.bulk_save_objects(batch_raw)
            session.flush()

            from sqlalchemy import select
            stmt = (
                select(MovimentacaoRaw)
                .where(MovimentacaoRaw.importacao_id == importacao.id)
                .order_by(MovimentacaoRaw.linha_excel)
            )
            raws_inseridas = session.execute(stmt).scalars().all()
            raw_id_por_linha: dict[int, int] = {r.linha_excel: r.id for r in raws_inseridas}

            repo_empresa = EmpresaRepository(session)
            repo_banco = BancoRepository(session)
            repo_banco.seed_padrao()
            repo_categoria = CategoriaRepository(session)

            cache_empresas: dict[str, int] = {}
            cache_bancos: dict[str, int] = {}
            cache_categorias: dict[str, int] = {}
            batch_mov: list[Movimentacao] = []

            for mov_norm in movs_para_inserir:
                empresa_nome = mov_norm.empresa
                if empresa_nome not in cache_empresas:
                    codigo = EMP_MAP_INVERSO.get(empresa_nome, f'_{empresa_nome[:3].upper()}')
                    empresa_obj = repo_empresa.get_or_create(codigo=codigo, nome=empresa_nome)
                    session.flush()
                    cache_empresas[empresa_nome] = empresa_obj.id
                empresa_id = cache_empresas[empresa_nome]

                banco_id = None
                banco_codigo = mov_norm.banco
                if banco_codigo:
                    if banco_codigo not in cache_bancos:
                        banco_obj = repo_banco.get_by_codigo(banco_codigo)
                        if banco_obj:
                            cache_bancos[banco_codigo] = banco_obj.id
                    banco_id = cache_bancos.get(banco_codigo)

                natureza = mov_norm.natureza
                if natureza not in cache_categorias:
                    prefixo = mov_norm.prefixo_categoria
                    grupo = mov_norm.grupo_categoria
                    cat_obj = repo_categoria.get_or_create(
                        nome=natureza,
                        codigo=prefixo,
                        grupo=grupo,
                    )
                    session.flush()
                    cache_categorias[natureza] = cat_obj.id
                categoria_id = cache_categorias[natureza]

                raw_id = raw_id_por_linha.get(mov_norm.linha_excel)

                mov = Movimentacao(
                    raw_id=raw_id,
                    importacao_id=importacao.id,
                    empresa_id=empresa_id,
                    banco_id=banco_id,
                    categoria_id=categoria_id,
                    data_transacao=mov_norm.data_transacao,
                    vencimento=mov_norm.vencimento,
                    titular=mov_norm.titular,
                    tipo=mov_norm.movimentacao,
                    valor=mov_norm.valor,
                    valor_absoluto=mov_norm.valor_absoluto,
                    documento=mov_norm.documento,
                    hash_registro=mov_norm.hash_registro,
                    is_duplicata=mov_norm.is_duplicata,
                    is_anomalia_data=mov_norm.is_anomalia_data,
                    em_aberto=mov_norm.em_aberto,
                    centro_custo=mov_norm.centro_custo,
                )
                batch_mov.append(mov)

                if len(batch_mov) >= BATCH_SIZE:
                    session.bulk_save_objects(batch_mov)
                    batch_mov.clear()

            if batch_mov:
                session.bulk_save_objects(batch_mov)

        # ── Etapa 9: Atualizar status para CONCLUIDA (100%) ─────────────────
        _progresso("Finalizando", 1.0, "Confirmando transação no banco...")
        elapsed = time.time() - inicio
        importacao.status = "CONCLUIDA"
        importacao.qtd_registros = len(movs_para_inserir) + len(atualizacoes)
        importacao.qtd_erros = len(erros_norm)
        importacao.qtd_duplicados = total_duplicatas_internas
        importacao.observacoes = (
            f"Importação concluída em {elapsed:.1f}s. "
            f"{len(movs_para_inserir):,} novos cadastrados. "
            f"{len(atualizacoes):,} atualizados. "
            f"{total_ja_existentes:,} inalterados (ignorados). "
            f"{total_duplicatas_internas:,} duplicatas internas sinalizadas."
        )
        session.commit()

        _progresso("Concluído", 1.0, "Importação realizada com sucesso!", concluida=True)

        return ResultadoImportacao(
            sucesso=True,
            importacao_id=importacao.id,
            arquivo=arquivo_path.name,
            total_lidos=len(movimentacoes_norm),
            total_importados=len(movs_para_inserir),
            total_atualizados=len(atualizacoes),
            total_erros=len(erros_norm),
            total_duplicatas=total_duplicatas_internas,
            total_ja_existentes=total_ja_existentes,
            total_em_aberto=total_em_aberto,
            mensagem=f"Importação concluída com sucesso em {elapsed:.1f}s.",
            detalhes=resultado_validacao.resumo_texto().split('\n'),
        )

    except Exception as exc:
        session.rollback()
        erro_msg = str(exc)
        _progresso("Erro", 1.0, erro_msg, concluida=True, erro=erro_msg)
        return ResultadoImportacao(
            sucesso=False,
            importacao_id=None,
            arquivo=str(caminho_arquivo),
            total_lidos=0,
            total_importados=0,
            total_atualizados=0,
            total_erros=1,
            total_duplicatas=0,
            total_ja_existentes=0,
            total_em_aberto=0,
            mensagem=f"Erro durante a importação: {erro_msg}",
            detalhes=[erro_msg],
        )


def sincronizar_movimentacoes_normalizadas(
    movimentacoes_norm: list[MovimentacaoNormalizada],
    session: Session,
    nome_origem: str = "Sisplan SQL",
    callback_progresso: Optional[Callable[[ProgressoImportacao], Any]] = None,
) -> ResultadoImportacao:
    """
    Executa a conciliação e sincronização de uma lista de MovimentacaoNormalizada
    (extraídas diretamente do banco SQL do Sisplan) com o banco de dados local.

    Aplica as regras:
        - UPDATE nos registros existentes que mudaram Vencimento, Valor ou Data de Pagamento.
        - INSERT nos registros novos com marcação de duplicatas internas.
        - IGNORA os registros que já estão idênticos no banco de dados.
    """
    inicio = time.time()

    def _progresso(etapa: str, prog: float, msg: str, concluida: bool = False, erro: str = None):
        if callback_progresso:
            callback_progresso(
                ProgressoImportacao(
                    etapa=etapa,
                    progresso=prog,
                    mensagem=msg,
                    concluida=concluida,
                    erro=erro,
                )
            )

    try:
        # Auto-backup
        _progresso("Backup automático", 0.05, "Criando backup de segurança...")
        criar_backup_automatico()

        if not movimentacoes_norm:
            return ResultadoImportacao(
                sucesso=True,
                importacao_id=None,
                arquivo=nome_origem,
                total_lidos=0,
                total_importados=0,
                total_atualizados=0,
                total_erros=0,
                total_duplicatas=0,
                total_ja_existentes=0,
                total_em_aberto=0,
                mensagem="Nenhum registro retornado pelo banco do Sisplan para o período selecionado.",
                detalhes=[],
            )

        # Conciliação com o banco local
        _progresso("Conciliando dados", 0.30, f"Conciliando {len(movimentacoes_norm):,} registros com o banco local...")
        hashes_banco, mapa_negocio_banco = carregar_banco_para_conciliacao(session)
        analise = processar_analise_importacao(movimentacoes_norm, hashes_banco, mapa_negocio_banco)

        movs_para_inserir = analise.novos_para_inserir
        atualizacoes = analise.atualizacoes
        total_ja_existentes = analise.ja_existentes_count
        total_duplicatas_internas = analise.duplicatas_internas_count

        # Expurgar registros órfãos / cancelados / desdobrados no período sincronizado
        # Importante: só expurga registros dos tipos presentes no lote sincronizado (ex: se sincronizou apenas RECEBER, não toca em PAGAR)
        vencimentos = [m.vencimento for m in movimentacoes_norm if m.vencimento]
        tipos_sincronizados = set(m.movimentacao for m in movimentacoes_norm if m.movimentacao)
        orfaos_para_excluir: list[Movimentacao] = []
        if vencimentos and tipos_sincronizados:
            min_venc = min(vencimentos)
            max_venc = max(vencimentos)

            chaves_sisplan = set(
                (m.empresa.strip().upper(), m.movimentacao, m.documento.strip().lstrip('0') if m.documento else '', m.vencimento)
                for m in movimentacoes_norm if m.documento
            )

            orfaos = session.query(Movimentacao).filter(
                Movimentacao.vencimento >= min_venc,
                Movimentacao.vencimento <= max_venc,
                Movimentacao.tipo.in_(tipos_sincronizados),
                Movimentacao.em_aberto == True
            ).all()

            for mov in orfaos:
                doc_clean = mov.documento.strip().lstrip('0') if mov.documento else ''
                emp_nome = mov.empresa.nome.strip().upper() if mov.empresa else ''
                k = (emp_nome, mov.tipo, doc_clean, mov.vencimento)
                if k not in chaves_sisplan:
                    orfaos_para_excluir.append(mov)

            # Também expurga duplicatas residuais de mesmo (empresa, tipo, doc) no período restrito aos tipos sincronizados
            movs_periodo = session.query(Movimentacao).filter(
                Movimentacao.vencimento >= min_venc,
                Movimentacao.vencimento <= max_venc,
                Movimentacao.tipo.in_(tipos_sincronizados),
            ).all()
            docs_vistos: dict[tuple, Movimentacao] = {}
            for mov in sorted(movs_periodo, key=lambda x: x.id, reverse=True):
                doc_clean = mov.documento.strip().lstrip('0') if mov.documento else ''
                if not doc_clean:
                    continue
                k_dup = (mov.empresa_id, mov.tipo, doc_clean)
                if k_dup in docs_vistos:
                    if mov not in orfaos_para_excluir:
                        orfaos_para_excluir.append(mov)
                else:
                    docs_vistos[k_dup] = mov

        if not movs_para_inserir and not atualizacoes and not orfaos_para_excluir:
            _progresso("Concluído", 1.0, "Todos os registros já estão atualizados no banco local.", concluida=True)
            return ResultadoImportacao(
                sucesso=True,
                importacao_id=None,
                arquivo=nome_origem,
                total_lidos=len(movimentacoes_norm),
                total_importados=0,
                total_atualizados=0,
                total_erros=0,
                total_duplicatas=0,
                total_ja_existentes=total_ja_existentes,
                total_em_aberto=0,
                mensagem=f"Todos os {total_ja_existentes:,} registros do Sisplan já estão atualizados no banco de dados local.",
                detalhes=["Nenhum registro novo ou alterado para sincronizar."],
            )

        # Se houver órfãos/cancelados a excluir, executa a exclusão
        if orfaos_para_excluir:
            for mov in orfaos_para_excluir:
                session.delete(mov)
            session.flush()

        # Registrar importação / sincronização
        _progresso("Registrando sincronização", 0.50, "Iniciando transação no banco de dados...")
        hash_lote = f"sisplan_sql_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        importacao = Importacao(
            arquivo=nome_origem,
            hash_arquivo=hash_lote,
            data_importacao=datetime.now(),
            qtd_registros=len(movs_para_inserir) + len(atualizacoes) + len(orfaos_para_excluir),
            qtd_erros=0,
            qtd_duplicados=total_duplicatas_internas,
            status="PENDENTE",
            observacoes=(
                f"Sincronização SQL Sisplan. {len(movs_para_inserir)} novos, "
                f"{len(atualizacoes)} atualizados, {len(orfaos_para_excluir)} cancelados/removidos, {total_ja_existentes} inalterados."
            ),
        )
        session.add(importacao)
        session.flush()

        # Atualizações (UPDATE)
        if atualizacoes:
            _progresso("Atualizando registros", 0.65, f"Atualizando {len(atualizacoes):,} registros existentes...")
            repo_cat_sync = CategoriaRepository(session)
            repo_bco_sync = BancoRepository(session)
            for item in atualizacoes:
                mov_bd = item.mov_banco
                m_norm = item.mov_norm

                mov_bd.vencimento = m_norm.vencimento
                mov_bd.valor = m_norm.valor
                mov_bd.valor_absoluto = m_norm.valor_absoluto
                mov_bd.data_transacao = m_norm.data_transacao
                mov_bd.em_aberto = m_norm.em_aberto
                mov_bd.titular = m_norm.titular
                mov_bd.hash_registro = m_norm.hash_registro
                mov_bd.is_anomalia_data = m_norm.is_anomalia_data
                mov_bd.centro_custo = m_norm.centro_custo
                mov_bd.importacao_id = importacao.id

                if m_norm.natureza:
                    cat_obj = repo_cat_sync.get_or_create(
                        nome=m_norm.natureza,
                        codigo=m_norm.prefixo_categoria,
                        grupo=m_norm.grupo_categoria,
                    )
                    mov_bd.categoria_id = cat_obj.id

                if m_norm.banco:
                    bco_obj = repo_bco_sync.get_by_codigo(m_norm.banco)
                    if bco_obj:
                        mov_bd.banco_id = bco_obj.id
            session.flush()

        # Inserções (INSERT)
        total_em_aberto = sum(1 for m in movs_para_inserir if m.em_aberto)

        if movs_para_inserir:
            _progresso("Salvando novos registros", 0.80, f"Persistindo {len(movs_para_inserir):,} registros novos...")
            batch_raw: list[MovimentacaoRaw] = []

            for m in movs_para_inserir:
                mov_raw = MovimentacaoRaw(
                    importacao_id=importacao.id,
                    empresa_original=m.empresa,
                    banco_original=m.banco or '',
                    movimentacao_original=m.movimentacao,
                    titular_original=m.titular or '',
                    natureza_original=m.natureza,
                    data_transacao_original=str(m.data_transacao or ''),
                    vencimento_original=str(m.vencimento or ''),
                    valor_original=str(m.valor),
                    documento_original=m.documento or None,
                    linha_excel=m.linha_excel,
                )
                batch_raw.append(mov_raw)

                if len(batch_raw) >= BATCH_SIZE:
                    session.bulk_save_objects(batch_raw)
                    batch_raw.clear()

            if batch_raw:
                session.bulk_save_objects(batch_raw)
            session.flush()

            from sqlalchemy import select
            stmt = (
                select(MovimentacaoRaw)
                .where(MovimentacaoRaw.importacao_id == importacao.id)
                .order_by(MovimentacaoRaw.linha_excel)
            )
            raws_inseridas = session.execute(stmt).scalars().all()
            raw_id_por_linha: dict[int, int] = {r.linha_excel: r.id for r in raws_inseridas}

            repo_empresa = EmpresaRepository(session)
            repo_banco = BancoRepository(session)
            repo_banco.seed_padrao()
            repo_categoria = CategoriaRepository(session)

            cache_empresas: dict[str, int] = {}
            cache_bancos: dict[str, int] = {}
            cache_categorias: dict[str, int] = {}
            batch_mov: list[Movimentacao] = []

            for mov_norm in movs_para_inserir:
                empresa_nome = mov_norm.empresa
                if empresa_nome not in cache_empresas:
                    codigo = EMP_MAP_INVERSO.get(empresa_nome, f'_{empresa_nome[:3].upper()}')
                    empresa_obj = repo_empresa.get_or_create(codigo=codigo, nome=empresa_nome)
                    session.flush()
                    cache_empresas[empresa_nome] = empresa_obj.id
                empresa_id = cache_empresas[empresa_nome]

                banco_id = None
                banco_codigo = mov_norm.banco
                if banco_codigo:
                    if banco_codigo not in cache_bancos:
                        banco_obj = repo_banco.get_by_codigo(banco_codigo)
                        if banco_obj:
                            cache_bancos[banco_codigo] = banco_obj.id
                    banco_id = cache_bancos.get(banco_codigo)

                natureza = mov_norm.natureza
                if natureza not in cache_categorias:
                    prefixo = mov_norm.prefixo_categoria
                    grupo = mov_norm.grupo_categoria
                    cat_obj = repo_categoria.get_or_create(
                        nome=natureza,
                        codigo=prefixo,
                        grupo=grupo,
                    )
                    session.flush()
                    cache_categorias[natureza] = cat_obj.id
                categoria_id = cache_categorias[natureza]

                raw_id = raw_id_por_linha.get(mov_norm.linha_excel)

                mov = Movimentacao(
                    raw_id=raw_id,
                    importacao_id=importacao.id,
                    empresa_id=empresa_id,
                    banco_id=banco_id,
                    categoria_id=categoria_id,
                    data_transacao=mov_norm.data_transacao,
                    vencimento=mov_norm.vencimento,
                    titular=mov_norm.titular,
                    tipo=mov_norm.movimentacao,
                    valor=mov_norm.valor,
                    valor_absoluto=mov_norm.valor_absoluto,
                    documento=mov_norm.documento,
                    hash_registro=mov_norm.hash_registro,
                    is_duplicata=mov_norm.is_duplicata,
                    is_anomalia_data=mov_norm.is_anomalia_data,
                    em_aberto=mov_norm.em_aberto,
                    centro_custo=mov_norm.centro_custo,
                )
                batch_mov.append(mov)

                if len(batch_mov) >= BATCH_SIZE:
                    session.bulk_save_objects(batch_mov)
                    batch_mov.clear()

            if batch_mov:
                session.bulk_save_objects(batch_mov)

        # Finalizar
        _progresso("Finalizando", 1.0, "Confirmando transação no banco local...")
        elapsed = time.time() - inicio
        importacao.status = "CONCLUIDA"
        importacao.qtd_registros = len(movs_para_inserir) + len(atualizacoes)
        importacao.qtd_erros = 0
        importacao.qtd_duplicados = total_duplicatas_internas
        importacao.observacoes = (
            f"Sincronização concluída em {elapsed:.1f}s. "
            f"{len(movs_para_inserir):,} novos cadastrados. "
            f"{len(atualizacoes):,} atualizados. "
            f"{total_ja_existentes:,} inalterados (ignorados). "
            f"{total_duplicatas_internas:,} duplicatas internas sinalizadas."
        )
        session.commit()

        _progresso("Concluído", 1.0, "Sincronização realizada com sucesso!", concluida=True)

        return ResultadoImportacao(
            sucesso=True,
            importacao_id=importacao.id,
            arquivo=nome_origem,
            total_lidos=len(movimentacoes_norm),
            total_importados=len(movs_para_inserir),
            total_atualizados=len(atualizacoes),
            total_erros=0,
            total_duplicatas=total_duplicatas_internas,
            total_ja_existentes=total_ja_existentes,
            total_em_aberto=total_em_aberto,
            mensagem=f"Sincronização com o Sisplan concluída com sucesso em {elapsed:.1f}s.",
            detalhes=[
                f"Novos cadastrados: {len(movs_para_inserir):,}",
                f"Existentes atualizados: {len(atualizacoes):,}",
                f"Inalterados mantidos: {total_ja_existentes:,}",
            ],
        )

    except Exception as exc:
        session.rollback()
        erro_msg = str(exc)
        _progresso("Erro", 1.0, erro_msg, concluida=True, erro=erro_msg)
        return ResultadoImportacao(
            sucesso=False,
            importacao_id=None,
            arquivo=nome_origem,
            total_lidos=len(movimentacoes_norm),
            total_importados=0,
            total_atualizados=0,
            total_erros=1,
            total_duplicatas=0,
            total_ja_existentes=0,
            total_em_aberto=0,
            mensagem=f"Erro durante a sincronização: {erro_msg}",
            detalhes=[erro_msg],
        )
