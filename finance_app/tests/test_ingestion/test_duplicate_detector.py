import pytest
from datetime import date
from finance_app.ingestion.normalizer import MovimentacaoNormalizada
from finance_app.ingestion.duplicate_detector import detectar_duplicatas, marcar_duplicatas

def create_mov(linha, hash_val, d=date(2024,1,1), t='T1', v=100.0):
    return MovimentacaoNormalizada(
        linha_excel=linha, empresa='EMP', movimentacao='PAGAR', titular=t,
        natureza='N1', prefixo_categoria='N', grupo_categoria='G',
        data_transacao=d, vencimento=d, valor=-v, valor_absoluto=v,
        em_aberto=False, is_anomalia_data=False, hash_registro=hash_val
    )

def test_sem_duplicatas():
    movs = [
        create_mov(1, 'h1', t='T1'),
        create_mov(2, 'h2', t='T2'),
        create_mov(3, 'h3', t='T3'),
        create_mov(4, 'h4', t='T4'),
        create_mov(5, 'h5', t='T5')
    ]
    res = detectar_duplicatas(movs)
    assert res.duplicatas_exatas == 0
    assert res.possiveis_duplicatas == 0

def test_duplicatas_exatas():
    movs = [
        create_mov(1, 'h1'),
        create_mov(2, 'h1'),
        create_mov(3, 'h1')
    ]
    res = detectar_duplicatas(movs)
    assert res.duplicatas_exatas == 2

def test_possiveis_duplicatas():
    movs = [
        create_mov(1, 'h1', d=date(2024,1,1), t='T1', v=100),
        create_mov(2, 'h2', d=date(2024,1,1), t='T1', v=100)
    ]
    res = detectar_duplicatas(movs)
    assert res.possiveis_duplicatas == 1
    assert res.duplicatas_exatas == 0

def test_marcar_duplicatas():
    movs = [
        create_mov(1, 'h1'),
        create_mov(2, 'h1'),
        create_mov(3, 'h1')
    ]
    res = detectar_duplicatas(movs)
    marcadas = marcar_duplicatas(movs, res)
    assert not marcadas[0].is_duplicata
    assert marcadas[1].is_duplicata
    assert marcadas[2].is_duplicata

def test_grupos_duplicatas():
    movs = [
        create_mov(1, 'h1'),
        create_mov(2, 'h1'),
        create_mov(3, 'h2'),
        create_mov(4, 'h2')
    ]
    res = detectar_duplicatas(movs)
    assert len(res.grupos_duplicatas) == 2

def test_resumo_texto():
    movs = [create_mov(1, 'h1'), create_mov(2, 'h1')]
    res = detectar_duplicatas(movs)
    txt = res.resumo_texto()
    assert "Total analisadas: 2" in txt
    assert "Duplicatas" in txt


def test_duplicatas_contra_banco():
    from finance_app.ingestion.duplicate_detector import (
        detectar_duplicatas_contra_banco,
        marcar_duplicatas_contra_banco,
    )
    movs = [
        create_mov(1, 'h1'),
        create_mov(2, 'h2'),
        create_mov(3, 'h3'),
    ]
    res = detectar_duplicatas_contra_banco(movs, {'h2', 'h9'})
    assert res.duplicatas_exatas == 1
    marcadas = marcar_duplicatas_contra_banco(movs, {'h2', 'h9'})
    assert not marcadas[0].is_duplicata
    assert marcadas[1].is_duplicata
    assert not marcadas[2].is_duplicata


def test_sem_duplicata_quando_banco_vazio():
    from finance_app.ingestion.duplicate_detector import detectar_duplicatas_contra_banco
    movs = [create_mov(1, 'h1'), create_mov(2, 'h1')]
    res = detectar_duplicatas_contra_banco(movs, set())
    assert res.duplicatas_exatas == 0
