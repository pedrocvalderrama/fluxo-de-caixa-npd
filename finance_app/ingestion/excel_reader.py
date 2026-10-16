"""
Leitura e extração de dados do arquivo Excel de fluxo de caixa.
"""
import hashlib
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
import openpyxl

from finance_app.config.settings import settings

# Mapeamento de nomes de colunas aceitos (flexível)
COLUMN_ALIASES = {
    'empresa': ['empresa', 'empresa ', 'company'],
    'banco': ['banco', 'banco ', 'bank', 'instituição financeira', 'instituicao financeira'],
    'movimentacao': ['movimentação', 'movimentacao', 'tipo', 'movimento'],
    'titular': ['titular', 'nome', 'razão social', 'razao social'],
    'natureza': ['natureza contábil', 'natureza contabil', 'categoria', 'desc_classe', 'natureza'],
    'data_transacao': ['data da transação', 'data da transacao', 'data pagto.', 'pagamento', 'data'],
    'vencimento': ['vencimento'],
    'valor': ['valor', 'valor pago', 'pago'],
    'documento': ['documento', 'número documento', 'numero documento', 'doc'],
}

# Fontes do identificador de título (contas a pagar / receber)
_COLUNAS_NUMERO = ['numero', 'número', 'nº', 'num']
_COLUNAS_DUPLICATA = ['duplicata']


def _encontrar_coluna(colunas: list[str], aliases: list[str]) -> Optional[str]:
    por_nome = {str(c).strip().lower(): c for c in colunas}
    for alias in aliases:
        if alias in por_nome:
            return por_nome[alias]
    return None


@dataclass
class ExcelReadResult:
    df_raw: pd.DataFrame          # DataFrame bruto exatamente como lido
    df_mapped: pd.DataFrame       # DataFrame com colunas padronizadas
    sheet_name: str               # Nome da aba lida
    total_rows: int               # Total de linhas (excluindo header)
    hash_arquivo: str             # SHA-256 do conteúdo do arquivo
    arquivo: str                  # Nome do arquivo
    mapeamento_colunas: dict      # {col_padrao: col_original}
    colunas_nao_mapeadas: list    # Colunas que não foram identificadas
    avisos: list[str] = field(default_factory=list)  # Avisos não críticos


def calcular_hash_arquivo(caminho: Path) -> str:
    """Calcula SHA-256 do arquivo em chunks de 8192 bytes."""
    sha256 = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def detectar_aba(wb: openpyxl.Workbook, nome_preferido: str = 'Fluxo de Caixa') -> Tuple[str, Optional[str]]:
    """Tenta encontrar a aba pelo nome exato, case-insensitive, ou usa a primeira."""
    sheet_names = wb.sheetnames
    
    if nome_preferido in sheet_names:
        return nome_preferido, None
        
    for sheet in sheet_names:
        if sheet.lower() == nome_preferido.lower():
            return sheet, f"Aba '{nome_preferido}' não encontrada. Usando '{sheet}' (case-insensitive)."
            
    primeira_aba = sheet_names[0]
    return primeira_aba, f"Aba preferida '{nome_preferido}' não encontrada. Usando a primeira aba: '{primeira_aba}'."

def _coalesce_documento(df_raw: pd.DataFrame) -> pd.Series:
    """Une Documento / Numero (pagar) / Duplicata (receber) em um único identificador."""
    col_documento = _encontrar_coluna(df_raw.columns.tolist(), COLUMN_ALIASES['documento'])
    col_numero = _encontrar_coluna(df_raw.columns.tolist(), _COLUNAS_NUMERO)
    col_duplicata = _encontrar_coluna(df_raw.columns.tolist(), _COLUNAS_DUPLICATA)

    def _limpo(col: Optional[str]) -> pd.Series:
        if col is None:
            return pd.Series([pd.NA] * len(df_raw), index=df_raw.index, dtype=object)

        def _para_texto(v):
            if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
                return pd.NA
            # Excel pode ler "000007" como float 7.0 — evita "7.0" no identificador
            if isinstance(v, float):
                if v.is_integer():
                    return str(int(v))
                return str(v).strip()
            if isinstance(v, int):
                return str(v)
            s = str(v).strip()
            if not s or s.lower() in ('nan', 'none', '<na>'):
                return pd.NA
            # Corrige resíduos tipo "7.0" vindos de float serializado
            if s.endswith('.0') and s.replace('.', '', 1).isdigit():
                return s[:-2]
            return s

        return df_raw[col].map(_para_texto)

    serie = _limpo(col_documento)
    serie = serie.fillna(_limpo(col_numero))
    serie = serie.fillna(_limpo(col_duplicata))
    return serie


def mapear_colunas(colunas_excel: list[str]) -> Tuple[Dict[str, str], List[str]]:
    """Mapeia colunas do Excel para colunas padrão usando COLUMN_ALIASES."""
    mapeamento = {}
    colunas_nao_mapeadas = []
    aliases_documento_fonte = set(_COLUNAS_NUMERO + _COLUNAS_DUPLICATA)

    for col_excel in colunas_excel:
        col_excel_limpa = str(col_excel).strip().lower()
        # Numero/Duplicata são coalescidos em 'documento' depois
        if col_excel_limpa in aliases_documento_fonte:
            continue
        encontrou = False
        for col_padrao, aliases in COLUMN_ALIASES.items():
            if col_excel_limpa in [a.lower() for a in aliases]:
                mapeamento[col_padrao] = col_excel
                encontrou = True
                break
        if not encontrou:
            colunas_nao_mapeadas.append(col_excel)

    return mapeamento, colunas_nao_mapeadas

def ler_excel(caminho_arquivo: str | Path) -> ExcelReadResult:
    """Lê arquivo excel validando-o e retornando um ExcelReadResult formatado."""
    caminho = Path(caminho_arquivo)
    if not caminho.exists() or caminho.suffix.lower() not in ['.xlsx']:
        raise ValueError(f"Arquivo inválido ou não encontrado: {caminho}")
        
    hash_arq = calcular_hash_arquivo(caminho)
    
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    nome_aba, aviso_aba = detectar_aba(wb)
    wb.close()

    # Preserva zeros à esquerda em Numero/Duplicata/Documento
    header = pd.read_excel(caminho, sheet_name=nome_aba, engine='openpyxl', nrows=0)
    aliases_texto = set(
        a.lower() for a in (
            COLUMN_ALIASES['documento'] + _COLUNAS_NUMERO + _COLUNAS_DUPLICATA
        )
    )
    dtype_texto = {
        c: str for c in header.columns
        if str(c).strip().lower() in aliases_texto
    }
    df_raw = pd.read_excel(
        caminho, sheet_name=nome_aba, engine='openpyxl', dtype=dtype_texto or None
    )
    
    mapeamento, col_nao_mapeadas = mapear_colunas(df_raw.columns.tolist())
    
    # Inverter mapeamento para usar em rename
    rename_dict = {col_excel: col_padrao for col_padrao, col_excel in mapeamento.items()}
    df_mapped = df_raw.rename(columns=rename_dict).copy()
    
    # Criar colunas faltantes com valores nulos
    for c in COLUMN_ALIASES.keys():
        if c not in df_mapped.columns:
            df_mapped[c] = None

    # Sempre prioriza coalesce de Numero/Duplicata (e Documento, se existir)
    df_mapped['documento'] = _coalesce_documento(df_raw)
            
    # Garantir a ordem final e selecionar apenas as colunas padrão
    ordem = list(COLUMN_ALIASES.keys())
    df_mapped = df_mapped[ordem].copy()
    
    # Adicionar a coluna indicando a linha do Excel
    # Assume que a linha 1 é o cabeçalho, então a primeira linha de dados seria a linha 2
    df_mapped['linha_excel'] = range(2, len(df_mapped) + 2)
    
    avisos = []
    if aviso_aba:
        avisos.append(aviso_aba)
    if df_mapped['documento'].notna().any():
        mapeamento['documento'] = 'Numero/Duplicata'
        
    return ExcelReadResult(
        df_raw=df_raw,
        df_mapped=df_mapped,
        sheet_name=nome_aba,
        total_rows=len(df_raw),
        hash_arquivo=hash_arq,
        arquivo=caminho.name,
        mapeamento_colunas=mapeamento,
        colunas_nao_mapeadas=col_nao_mapeadas,
        avisos=avisos
    )

def gerar_preview(df: pd.DataFrame, max_rows: Optional[int] = None) -> pd.DataFrame:
    """Retorna preview formatado das primeiras max_rows."""
    limite = max_rows if max_rows is not None else getattr(settings, 'MAX_PREVIEW_ROWS', 100)
    return df.head(limite).copy()
