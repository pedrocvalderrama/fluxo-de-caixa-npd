"""Utilitários para manipulação de moeda brasileira."""
import math
from typing import Optional, Tuple

def formatar_moeda(valor: float | int | None, com_simbolo: bool = True) -> str:
    """Formata um valor como moeda brasileira."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        valor = 0.0
    prefixo = "R$ " if com_simbolo else ""
    sinal = "-" if valor < 0 else ""
    abs_valor = abs(valor)
    
    inteiro, decimal = f"{abs_valor:.2f}".split(".")
    
    inteiro_formatado = ""
    while len(inteiro) > 3:
        inteiro_formatado = "." + inteiro[-3:] + inteiro_formatado
        inteiro = inteiro[:-3]
    inteiro_formatado = inteiro + inteiro_formatado
    
    if sinal and prefixo:
        return f"{prefixo}{sinal}{inteiro_formatado},{decimal}"
    return f"{sinal}{prefixo}{inteiro_formatado},{decimal}"

def formatar_moeda_resumida(valor: float | int | None) -> str:
    """Formata números grandes de forma abreviada (K, M, B)."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "R$ 0"
    abs_valor = abs(valor)
    sinal = "-" if valor < 0 else ""
    prefixo = "R$ "
    
    if abs_valor >= 1_000_000_000:
        return f"{sinal}{prefixo}{abs_valor / 1_000_000_000:.1f}B".replace(".", ",")
    elif abs_valor >= 1_000_000:
        return f"{sinal}{prefixo}{abs_valor / 1_000_000:.1f}M".replace(".", ",")
    elif abs_valor >= 1_000:
        return f"{sinal}{prefixo}{abs_valor / 1_000:.1f}K".replace(".", ",")
    else:
        num = f"{abs_valor:.0f}"
        return f"{sinal}{prefixo}{num}"

def parse_valor_br(texto: str) -> float | None:
    """Faz o parse do formato numérico brasileiro para float."""
    if not isinstance(texto, str):
        return None
    texto = texto.strip().replace("R$", "").strip()
    if not texto:
        return None
    
    if "." in texto and "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    elif "." in texto and len(texto.split(".")[-1]) == 3:
        texto = texto.replace(".", "")
        
    try:
        return float(texto)
    except ValueError:
        return None

def parse_valor_excel(valor) -> float | None:
    """Faz o parse de valores numéricos oriundos do Excel."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        if math.isnan(valor):
            return None
        return float(valor)
    if isinstance(valor, str):
        return parse_valor_br(valor)
    return None

def formatar_percentual(valor: float | None, casas: int = 1) -> str:
    """Formata um valor como percentual."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "0,0%"
    fmt = f"{{:.{casas}f}}"
    return fmt.format(valor).replace(".", ",") + "%"

def formatar_variacao(valor: float | None) -> tuple[str, str]:
    """Formata como variação com sinal, retornando texto e cor."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        valor = 0.0
    texto = formatar_percentual(abs(valor), 1)
    if valor > 0:
        return f"+{texto}", "green"
    elif valor < 0:
        return f"-{texto}", "red"
    else:
        return "0,0%", "gray"

def variacao_percentual(atual: float, anterior: float) -> float | None:
    """Calcula a variação percentual entre dois valores."""
    if not anterior:
        return None
    return ((atual - anterior) / anterior) * 100
