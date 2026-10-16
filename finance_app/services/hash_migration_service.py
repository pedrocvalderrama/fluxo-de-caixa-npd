"""
Recalcula hash_registro e flags is_duplicata com o critério atual
(vencimento + documento Numero/Duplicata).
"""
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import select

from finance_app.database.models import Movimentacao, Empresa, Banco, Categoria
from finance_app.ingestion.normalizer import calcular_hash_registro


def recalcular_hashes_e_duplicatas(session: Session) -> dict:
    """
    Atualiza hash_registro de todas as movimentações usando vencimento + documento
    e remarca is_duplicata (1º do grupo = False, demais = True).
    """
    empresas = {e.id: e.nome for e in session.query(Empresa).all()}
    bancos = {b.id: b.codigo for b in session.query(Banco).all()}
    categorias = {c.id: c.nome for c in session.query(Categoria).all()}

    movs = list(
        session.scalars(select(Movimentacao).order_by(Movimentacao.id)).all()
    )
    if not movs:
        return {"total": 0, "duplicatas": 0, "grupos": 0}

    por_hash: dict[str, list] = defaultdict(list)
    for mov in movs:
        empresa = empresas.get(mov.empresa_id, "")
        banco = bancos.get(mov.banco_id) if mov.banco_id else None
        natureza = categorias.get(mov.categoria_id, "") if mov.categoria_id else ""
        novo_hash = calcular_hash_registro(
            empresa=empresa,
            movimentacao=mov.tipo,
            titular=mov.titular,
            natureza=natureza,
            vencimento=mov.vencimento,
            valor=float(mov.valor or 0.0),
            banco=banco,
            documento=getattr(mov, "documento", None),
        )
        mov.hash_registro = novo_hash
        mov.is_duplicata = False
        por_hash[novo_hash].append(mov)

    total_dup = 0
    grupos = 0
    for grupo in por_hash.values():
        if len(grupo) < 2:
            continue
        grupos += 1
        # Mantém o primeiro (menor id) como referência
        grupo_ordenado = sorted(grupo, key=lambda m: m.id)
        for mov in grupo_ordenado[1:]:
            mov.is_duplicata = True
            total_dup += 1

    session.flush()
    return {"total": len(movs), "duplicatas": total_dup, "grupos": grupos}
