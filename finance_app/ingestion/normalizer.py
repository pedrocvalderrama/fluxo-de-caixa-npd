"""
Normalização dos dados extraídos do Excel para o modelo de dados.
"""
import hashlib
import traceback
import pandas as pd
from datetime import date
from dataclasses import dataclass, field
from typing import Optional

from finance_app.utils.dates import parse_data_excel, is_data_anomala
from finance_app.utils.formatting import extrair_prefixo_categoria, grupo_categoria, normalizar_texto
from finance_app.config.bancos import resolver_codigo_banco

@dataclass 
class MovimentacaoNormalizada:
    linha_excel: int
    empresa: str
    movimentacao: str          # 'PAGAR' ou 'RECEBER'
    titular: Optional[str]
    natureza: str
    prefixo_categoria: Optional[str]
    grupo_categoria: str
    data_transacao: Optional[date]
    vencimento: Optional[date]
    valor: float               # Com sinal (negativo para PAGAR)
    valor_absoluto: float      # Sempre positivo
    em_aberto: bool            # True se sem data_transacao
    is_anomalia_data: bool     # True se vencimento ou data_transacao for anômala
    hash_registro: str         # SHA-256 para deduplicação
    banco: Optional[str] = None  # Código interno (001, 033, 748) ou None
    documento: Optional[str] = None  # Numero (pagar) ou Duplicata (receber)
    centro_custo: Optional[str] = None  # Nome do Centro de Custo / Setor
    is_duplicata: bool = False # Para marcar após detecção

def calcular_hash_registro(
    empresa: str,
    movimentacao: str,
    titular: Optional[str],
    natureza: str,
    vencimento: Optional[date],
    valor: float,
    banco: Optional[str] = None,
    documento: Optional[str] = None,
) -> str:
    """Hash de deduplicação: inclui documento (Numero/Duplicata) quando disponível."""
    campos = [
        str(empresa),
        str(banco) if banco is not None else 'None',
        str(movimentacao),
        str(titular) if titular is not None else 'None',
        str(natureza),
        vencimento.isoformat() if vencimento is not None else 'None',
        str(valor),
        str(documento) if documento is not None else 'None',
    ]
    texto = '|'.join(campos)
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()

def normalizar_linha(row) -> MovimentacaoNormalizada:
    linha_excel = getattr(row, 'linha_excel', 0)
    try:
        empresa = normalizar_texto(getattr(row, 'empresa', '')).strip().upper()
        banco_raw = getattr(row, 'banco', None)
        banco_texto = None if (banco_raw is None or (isinstance(banco_raw, float) and pd.isna(banco_raw))) else str(banco_raw)
        banco = resolver_codigo_banco(banco_texto)
        movimentacao = normalizar_texto(getattr(row, 'movimentacao', '')).strip().upper()
        
        titular_raw = getattr(row, 'titular', None)
        titular = str(titular_raw).strip() if pd.notna(titular_raw) else None
        
        natureza_raw = getattr(row, 'natureza', '')
        natureza = str(natureza_raw).strip() if pd.notna(natureza_raw) else ''
        
        documento_raw = getattr(row, 'documento', None)
        if documento_raw is None or (isinstance(documento_raw, float) and pd.isna(documento_raw)):
            documento = None
        else:
            documento = str(documento_raw).strip() or None
            if documento and documento.lower() in ('nan', 'none', '<na>'):
                documento = None
        
        data_transacao_raw = getattr(row, 'data_transacao', None)
        data_transacao = parse_data_excel(data_transacao_raw)
        
        vencimento_raw = getattr(row, 'vencimento', None)
        vencimento = parse_data_excel(vencimento_raw)
        
        valor_raw = getattr(row, 'valor', 0.0)
        try:
            valor_float = float(valor_raw) if pd.notna(valor_raw) else 0.0
        except ValueError:
            valor_float = 0.0
            
        valor_absoluto = abs(valor_float)
        valor = valor_absoluto if movimentacao == 'RECEBER' else -valor_absoluto
        
        em_aberto = data_transacao is None
        is_anomalia_dt = is_data_anomala(data_transacao) if data_transacao else False
        is_anomalia_ven = is_data_anomala(vencimento) if vencimento else False
        is_anomalia = is_anomalia_dt or is_anomalia_ven
        
        prefixo, _ = extrair_prefixo_categoria(natureza)
        grupo = grupo_categoria(prefixo)
        
        hash_reg = calcular_hash_registro(
            empresa, movimentacao, titular, natureza, vencimento, valor, banco, documento
        )
        
        return MovimentacaoNormalizada(
            linha_excel=linha_excel,
            empresa=empresa,
            banco=banco,
            documento=documento,
            movimentacao=movimentacao,
            titular=titular,
            natureza=natureza,
            prefixo_categoria=prefixo,
            grupo_categoria=grupo,
            data_transacao=data_transacao,
            vencimento=vencimento,
            valor=valor,
            valor_absoluto=valor_absoluto,
            em_aberto=em_aberto,
            is_anomalia_data=is_anomalia,
            hash_registro=hash_reg
        )
    except Exception as e:
        raise e

def normalizar_dataframe(df: pd.DataFrame) -> tuple[list[MovimentacaoNormalizada], list[dict]]:
    normalizadas = []
    erros = []
    
    for row in df.itertuples(index=False):
        try:
            norm = normalizar_linha(row)
            normalizadas.append(norm)
        except Exception as e:
            linha = getattr(row, 'linha_excel', 0)
            erros.append({
                'linha_excel': linha,
                'erro': str(e),
                'traceback_str': traceback.format_exc()
            })
            
    return normalizadas, erros
