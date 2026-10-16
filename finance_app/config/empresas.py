"""
Cadastro padrão das empresas e função de ordenação oficial.
"""
from typing import Any

# Ordem oficial solicitada para exibição em todo o sistema:
# 1. NPD
# 2. Compre Sacola (COMPRE)
# 3. CS (CS Embalagens)
ORDEM_EMPRESAS_OFICIAL = ["NPD", "COMPRE", "CS"]


def ordem_empresa_chave(empresa_ou_nome: Any) -> tuple[int, str]:
    """
    Retorna uma tupla (prioridade, nome) para garantir ordenação consistente:
    1: NPD
    2: COMPRE / Compre Sacola
    3: CS
    99: Demais (ex: DEMO)
    """
    if hasattr(empresa_ou_nome, "nome"):
        nome = str(empresa_ou_nome.nome).strip().upper()
    elif isinstance(empresa_ou_nome, str):
        nome = empresa_ou_nome.strip().upper()
    else:
        nome = str(empresa_ou_nome).strip().upper()

    if "NPD" in nome:
        return (1, nome)
    if "COMPRE" in nome or "SACOLA" in nome:
        return (2, nome)
    if "CS" in nome:
        return (3, nome)
    return (99, nome)
