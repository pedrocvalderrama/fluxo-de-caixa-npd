import sys
sys.path.insert(0, r'c:\dev\FLUXO DE CAIXA')

from finance_app.ingestion.excel_reader import ler_excel, gerar_preview
from finance_app.ingestion.validator import validar_dataframe

# Ler o arquivo real
result = ler_excel(r'c:\dev\FLUXO DE CAIXA\FLUXODECAIXA.xlsx')
print(f'Hash: {result.hash_arquivo[:16]}...')
print(f'Aba: {result.sheet_name}')
print(f'Total rows: {result.total_rows}')
print(f'Colunas mapeadas: {result.mapeamento_colunas}')
print(f'Colunas não mapeadas: {result.colunas_nao_mapeadas}')
print(f'Avisos leitura: {result.avisos}')
print(f'\nColunas do df_mapped: {result.df_mapped.columns.tolist()}')
print(f'\nPrimeiras 3 linhas df_mapped:')
print(result.df_mapped[['empresa','movimentacao','titular','natureza','data_transacao','vencimento','valor','linha_excel']].head(3).to_string())

# Validar
validacao = validar_dataframe(result.df_mapped)
print(f'\n=== VALIDAÇÃO ===')
print(validacao.resumo_texto())
print(f'Pode importar: {validacao.pode_importar}')
print(f'Primeiros 5 problemas:')
for p in validacao.problemas[:5]:
    print(f'  Linha {p.linha}: [{p.severidade.value}] {p.coluna} - {p.mensagem}')
