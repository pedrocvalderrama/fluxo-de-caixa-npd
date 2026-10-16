__test__ = False
import sys
sys.path.insert(0, r'c:\dev\FLUXO DE CAIXA')

from finance_app.ingestion.excel_reader import ler_excel
from finance_app.ingestion.normalizer import normalizar_dataframe
from finance_app.ingestion.duplicate_detector import detectar_duplicatas, marcar_duplicatas
import time

print('Lendo Excel...')
result = ler_excel(r'c:\dev\FLUXO DE CAIXA\FLUXODECAIXA.xlsx')

print('Normalizando...')
t0 = time.time()
normalizadas, erros = normalizar_dataframe(result.df_mapped)
print(f'Normalizadas: {len(normalizadas)} em {time.time()-t0:.2f}s')
print(f'Erros de normalização: {len(erros)}')

# Verificar normalização
pagar = [m for m in normalizadas if m.movimentacao == 'PAGAR']
receber = [m for m in normalizadas if m.movimentacao == 'RECEBER']
em_aberto = [m for m in normalizadas if m.em_aberto]
anomalia_data = [m for m in normalizadas if m.is_anomalia_data]

print(f'\nPAGAR: {len(pagar)} (valores devem ser negativos)')
print(f'RECEBER: {len(receber)} (valores devem ser positivos)')
print(f'Em aberto: {len(em_aberto)}')
print(f'Anomalia data: {len(anomalia_data)}')

# Verificar sinais
primeiro_pagar = next(m for m in normalizadas if m.movimentacao == 'PAGAR' and m.valor != 0)
print(f'\nExemplo PAGAR: valor={primeiro_pagar.valor}, valor_absoluto={primeiro_pagar.valor_absoluto}')
assert primeiro_pagar.valor < 0, 'PAGAR deve ter valor negativo!'

primeiro_receber = next(m for m in normalizadas if m.movimentacao == 'RECEBER' and m.valor != 0)
print(f'Exemplo RECEBER: valor={primeiro_receber.valor}, valor_absoluto={primeiro_receber.valor_absoluto}')
assert primeiro_receber.valor > 0, 'RECEBER deve ter valor positivo!'

# Verificar hash
print(f'\nExemplo hash: {normalizadas[0].hash_registro[:16]}...')
assert len(normalizadas[0].hash_registro) == 64

# Verificar natureza normalizada
fretes = [m for m in normalizadas if 'FRETES' in (m.natureza or '')]
if fretes:
    print(f'Exemplo natureza: "{fretes[0].natureza}" (sem espaços finais: {not fretes[0].natureza.endswith(" ")})')
    assert not fretes[0].natureza.endswith(' '), 'Natureza com espaço final!'

print('\nDetectando duplicatas...')
t0 = time.time()
resultado_dup = detectar_duplicatas(normalizadas)
print(f'Detecção em {time.time()-t0:.2f}s')
print(resultado_dup.resumo_texto())

print('\nMarcando duplicatas...')
marcadas = marcar_duplicatas(normalizadas, resultado_dup)
dup_marcadas = [m for m in marcadas if hasattr(m, 'is_duplicata_marcada') or True]
print(f'Total marcadas: {len(marcadas)}')

print('\nTODOS OS TESTES PASSARAM!')
