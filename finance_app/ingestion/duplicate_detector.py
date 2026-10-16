"""
Detecção de duplicatas e conciliação de atualizações entre a planilha Excel e o banco SQL.

Chave de identificação do título: (Tipo, Numero/Duplicata, Natureza Contábil).

Cenários:
1. Registros inalterados (mesmo doc, mesma natureza, mesmo vencimento, mesmo valor e mesma data_transacao -> Ignorar).
2. Registros atualizados (mesmo doc e natureza, mas Vencimento, Valor ou Data da Transação mudou -> UPDATE no BD).
3. Registros novos (inseridos no banco SQL).
4. Duplicatas internas entre os registros novos (inseridos no banco SQL com is_duplicata=True).
"""
from dataclasses import dataclass, replace
from typing import Optional, Any
from collections import defaultdict

from finance_app.ingestion.normalizer import MovimentacaoNormalizada


@dataclass
class ItemAtualizacao:
    mov_banco: Any                         # Instância de Movimentacao existente no BD
    mov_norm: MovimentacaoNormalizada      # Dados novos vindos da planilha


@dataclass
class ResultadoAnaliseImportacao:
    total_lidos: int
    ja_existentes_count: int                        # Inalterados -> Ignorar
    atualizacoes: list[ItemAtualizacao]             # Mudou vencimento, valor ou data_transacao -> UPDATE no BD
    novos_para_inserir: list[MovimentacaoNormalizada]# Registros novos -> INSERT no BD
    duplicatas_internas_count: int                  # Novos repetidos entre si -> INSERT com is_duplicata=True

    @property
    def duplicatas_exatas(self) -> int:
        return self.ja_existentes_count

    @property
    def ja_no_banco_count(self) -> int:
        return self.ja_existentes_count

    def resumo_texto(self) -> str:
        return (
            f"Total lidos: {self.total_lidos}\n"
            f"Inalterados no banco (ignorados): {self.ja_existentes_count}\n"
            f"Atualizações (UPDATE): {len(self.atualizacoes)}\n"
            f"Novos a inserir (INSERT): {len(self.novos_para_inserir)}\n"
            f"Duplicatas internas (sinalizadas): {self.duplicatas_internas_count}"
        )


def processar_analise_importacao(
    movimentacoes_norm: list[MovimentacaoNormalizada],
    hashes_banco: set[str],
    mapa_negocio_banco: dict[tuple, Any],
) -> ResultadoAnaliseImportacao:
    """
    Classifica cada registro da planilha:
    1. Se hash bateu no banco -> Inalterado (Ignora).
    2. Se chave de negócio bateu (tipo, doc_clean, natureza_clean):
       - Se Vencimento, Valor ou Data de Transação mudou -> Atualização (UPDATE no BD existente).
       - Senão -> Inalterado (Ignora).
    3. Senão -> Registro novo (INSERT).
    """
    ja_existentes_count = 0
    atualizacoes: list[ItemAtualizacao] = []
    novos: list[MovimentacaoNormalizada] = []

    for m in movimentacoes_norm:
        # 1. Verificar por Hash Exato no banco SQL
        if m.hash_registro and m.hash_registro in hashes_banco:
            if isinstance(hashes_banco, dict):
                mov_bd = hashes_banco[m.hash_registro]
                # Verifica se propriedades mutáveis mudaram (ex: título foi pago ou renegociado)
                dt_mudou = (getattr(mov_bd, 'data_transacao', None) != m.data_transacao)
                em_aberto_mudou = (getattr(mov_bd, 'em_aberto', False) != m.em_aberto)
                if dt_mudou or em_aberto_mudou:
                    atualizacoes.append(ItemAtualizacao(mov_banco=mov_bd, mov_norm=m))
                    continue
            ja_existentes_count += 1
            continue

        # 2. Verificar por Chave de Negócio: (empresa, tipo, doc_clean)
        doc_clean = m.documento.strip().lstrip('0') if m.documento else ''
        nat_clean = m.natureza.strip().upper() if m.natureza else ''
        emp_clean = m.empresa.strip().upper() if m.empresa else ''
        chave_emp_doc = (emp_clean, m.movimentacao, doc_clean)
        chave_completa = (emp_clean, m.movimentacao, doc_clean, nat_clean)
        chave_tipo_doc = (m.movimentacao, doc_clean)
        chave_legado = (m.movimentacao, doc_clean, nat_clean)

        mov_bd = (
            mapa_negocio_banco.get(chave_emp_doc)
            or mapa_negocio_banco.get(chave_completa)
            or mapa_negocio_banco.get(chave_tipo_doc)
            or mapa_negocio_banco.get(chave_legado)
        )

        if doc_clean and mov_bd:
            # Verificar alterações nas propriedades mutáveis
            valor_bd = getattr(mov_bd, 'valor_absoluto', 0.0) or 0.0
            data_trans_bd = getattr(mov_bd, 'data_transacao', None)
            venc_bd = getattr(mov_bd, 'vencimento', None)
            em_aberto_bd = getattr(mov_bd, 'em_aberto', False)
            titular_bd = getattr(mov_bd, 'titular', '') or ''
            cat_bd_nome = getattr(mov_bd, '_categoria_nome', None)
            if cat_bd_nome is None:
                try:
                    cat_bd_nome = getattr(getattr(mov_bd, 'categoria', None), 'nome', '') or ''
                except Exception:
                    cat_bd_nome = ''
            cc_bd = getattr(mov_bd, 'centro_custo', None)

            venc_mudou = (venc_bd != m.vencimento)
            valor_mudou = abs(round(valor_bd, 2) - round(m.valor_absoluto, 2)) > 0.009
            data_trans_mudou = (data_trans_bd != m.data_transacao)
            em_aberto_mudou = (em_aberto_bd != m.em_aberto)
            cat_mudou = (cat_bd_nome.strip().upper() != nat_clean) if nat_clean and cat_bd_nome else False
            titular_mudou = (titular_bd.strip().upper() != (m.titular or '').strip().upper()) if m.titular else False
            cc_mudou = (cc_bd != m.centro_custo)

            if venc_mudou or valor_mudou or data_trans_mudou or em_aberto_mudou or cat_mudou or titular_mudou or cc_mudou:
                atualizacoes.append(ItemAtualizacao(mov_banco=mov_bd, mov_norm=m))
            else:
                ja_existentes_count += 1
        else:
            # É um registro novo
            novos.append(m)

    # 3. Processar duplicatas internas entre os registros NOVOS
    vistos_hash: set[str] = set()
    vistos_comb: set[tuple] = set()
    novos_processados: list[MovimentacaoNormalizada] = []
    duplicatas_internas_count = 0

    for m in novos:
        doc_clean = m.documento.strip().lstrip('0') if m.documento else ''
        nat_clean = m.natureza.strip().upper() if m.natureza else ''
        chave_comb = (m.movimentacao, doc_clean, nat_clean)

        is_dup_interna = False
        if m.hash_registro and m.hash_registro in vistos_hash:
            is_dup_interna = True
        elif doc_clean and nat_clean and chave_comb in vistos_comb:
            is_dup_interna = True

        if is_dup_interna:
            novos_processados.append(replace(m, is_duplicata=True))
            duplicatas_internas_count += 1
        else:
            if m.hash_registro:
                vistos_hash.add(m.hash_registro)
            if doc_clean and nat_clean:
                vistos_comb.add(chave_comb)
            novos_processados.append(replace(m, is_duplicata=False) if m.is_duplicata else m)

    return ResultadoAnaliseImportacao(
        total_lidos=len(movimentacoes_norm),
        ja_existentes_count=ja_existentes_count,
        atualizacoes=atualizacoes,
        novos_para_inserir=novos_processados,
        duplicatas_internas_count=duplicatas_internas_count,
    )


# --- Funções mantidas para compatibilidade com partes existentes ---

def processar_duplicatas_e_filtrar_banco(
    movimentacoes: list[MovimentacaoNormalizada],
    hashes_no_banco: set[str],
) -> ResultadoAnaliseImportacao:
    return processar_analise_importacao(movimentacoes, hashes_no_banco, {})


def detectar_duplicatas_contra_banco(
    movimentacoes: list[MovimentacaoNormalizada],
    hashes_no_banco: set[str],
) -> ResultadoAnaliseImportacao:
    return processar_analise_importacao(movimentacoes, hashes_no_banco, {})


def marcar_duplicatas_contra_banco(
    movimentacoes: list[MovimentacaoNormalizada],
    hashes_no_banco: set[str],
) -> list[MovimentacaoNormalizada]:
    marcadas = []
    for m in movimentacoes:
        if m.hash_registro in hashes_no_banco:
            marcadas.append(replace(m, is_duplicata=True))
        else:
            marcadas.append(replace(m, is_duplicata=False) if m.is_duplicata else m)
    return marcadas


@dataclass
class ResultadoDuplicatas:
    total_analisadas: int
    duplicatas_exatas: int
    possiveis_duplicatas: int
    indices_duplicatas_exatas: set[int]
    grupos_duplicatas: dict[str, list[int]]

    def resumo_texto(self) -> str:
        return (
            f"Total analisadas: {self.total_analisadas}\n"
            f"Duplicatas exatas: {self.duplicatas_exatas}\n"
            f"Possíveis duplicatas: {self.possiveis_duplicatas}"
        )


def detectar_duplicatas(movimentacoes: list[MovimentacaoNormalizada]) -> ResultadoDuplicatas:
    """Detecção legado para testes unitários."""
    grupos_hash = defaultdict(list)
    for idx, m in enumerate(movimentacoes):
        grupos_hash[m.hash_registro].append(idx)

    indices_duplicatas_exatas = set()
    grupos_dup_exatas = {}
    duplicatas_exatas = 0

    for h, idxs in grupos_hash.items():
        if len(idxs) > 1:
            duplicatas_exatas += len(idxs) - 1
            indices_duplicatas_exatas.update(idxs[1:])
            grupos_dup_exatas[h] = idxs

    # Possíveis duplicatas (mesma data, titular e valor)
    grupos_pos = defaultdict(list)
    for idx, m in enumerate(movimentacoes):
        if idx not in indices_duplicatas_exatas:
            k = (m.data_transacao or m.vencimento, m.titular, m.valor_absoluto)
            grupos_pos[k].append(idx)

    possiveis = 0
    for k, idxs in grupos_pos.items():
        if len(idxs) > 1:
            possiveis += len(idxs) - 1

    return ResultadoDuplicatas(
        total_analisadas=len(movimentacoes),
        duplicatas_exatas=duplicatas_exatas,
        possiveis_duplicatas=possiveis,
        indices_duplicatas_exatas=indices_duplicatas_exatas,
        grupos_duplicatas=grupos_dup_exatas,
    )


def marcar_duplicatas(
    movimentacoes: list[MovimentacaoNormalizada],
    resultado: ResultadoDuplicatas,
) -> list[MovimentacaoNormalizada]:
    """Marca is_duplicata nas movimentações com base no resultado da detecção."""
    marcadas = []
    for idx, m in enumerate(movimentacoes):
        if idx in resultado.indices_duplicatas_exatas:
            marcadas.append(replace(m, is_duplicata=True))
        else:
            marcadas.append(replace(m, is_duplicata=False))
    return marcadas

