"""Utilitários gerais de formatação para o sistema financeiro."""
import re
from typing import Optional, Tuple

def formatar_numero(valor: float | int | None, casas: int = 0) -> str:
    """Formata um número com separadores de milhar brasileiros."""
    if valor is None:
        valor = 0
    
    fmt = f"{{:,.{casas}f}}"
    texto = fmt.format(valor)
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")

def truncar_texto(texto: str | None, max_chars: int = 50) -> str:
    """Trunca um texto adicionando reticências."""
    if not texto:
        return ""
    if len(texto) <= max_chars:
        return texto
    return texto[:max_chars-3] + "..."

def normalizar_texto(texto: str | None) -> str | None:
    """Remove espaços em branco nas pontas e normaliza espaços internos."""
    if texto is None:
        return None
    return re.sub(r'\s+', ' ', str(texto)).strip()

def extrair_prefixo_categoria(nome_categoria: str) -> tuple[str | None, str]:
    """Extrai o prefixo e a descrição do nome da categoria."""
    if not nome_categoria:
        return None, ""
    match = re.match(r'^([A-Z]+)\s*-\s*(.+)$', nome_categoria)
    if match:
        return match.group(1), match.group(2).strip()
    return None, nome_categoria.strip()

def grupo_categoria(prefixo: str | None) -> str:
    """Mapeia um prefixo de categoria para o nome do grupo."""
    mapeamento = {
        "FR": "Fretes",
        "DF": "Desp. Financeiras",
        "IMP": "Impostos",
        "COM": "Comercial",
        "DC": "Desp. Comerciais",
        "CLI": "Clichês",
        "FUN": "Funcionários",
        "MP": "Matéria-Prima",
        "ST": "Serviços Terceiros",
        "RET": "Retiradas",
        "DG": "Desp. Gerais",
        "EST": "Estoque/Devoluções",
        "EMP": "Empréstimos",
        "INV": "Investimentos",
        "TERC": "Terceirização"
    }
    if not prefixo:
        return "Outros"
    return mapeamento.get(prefixo.upper(), "Outros")

def cor_variacao(valor: float | None) -> str:
    """Retorna cor CSS para o valor da variação."""
    if valor is None:
        return "gray"
    if valor > 0:
        return "green"
    elif valor < 0:
        return "red"
    return "gray"

def icone_tendencia(valor: float | None) -> str:
    """Retorna um emoji para a tendência."""
    if valor is None:
        return "➡️"
    if valor > 0:
        return "📈"
    elif valor < 0:
        return "📉"
    return "➡️"
