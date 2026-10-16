"""Cadastro padrão dos bancos da empresa e resolução de nomes/códigos."""
from typing import Optional

BANCOS_PADRAO: list[tuple[str, str]] = [
    ("001", "Banco do Brasil"),
    ("033", "Santander"),
    ("748", "Sicred"),
]

# Aliases aceitos na planilha (já normalizados em maiúsculas)
BANCO_ALIASES: dict[str, str] = {
    "001": "001",
    "BB": "001",
    "BANCO DO BRASIL": "001",
    "BANCO BRASIL": "001",
    "BRASIL": "001",
    "033": "033",
    "SANTANDER": "033",
    "748": "748",
    "SICRED": "748",
    "SICREDI": "748",
}

_PALAVRAS_CHAVE: list[tuple[str, str]] = [
    ("BANCO DO BRASIL", "001"),
    ("SANTANDER", "033"),
    ("SICREDI", "748"),
    ("SICRED", "748"),
]


def resolver_codigo_banco(valor: Optional[str]) -> Optional[str]:
    """Converte o texto da planilha no código interno (001, 033, 748) ou None."""
    if valor is None:
        return None
    texto = str(valor).strip().upper()
    if not texto or texto in {"NAN", "NONE", "NAT"}:
        return None
    if texto in BANCO_ALIASES:
        return BANCO_ALIASES[texto]
    for chave, codigo in _PALAVRAS_CHAVE:
        if chave in texto:
            return codigo
    return None
