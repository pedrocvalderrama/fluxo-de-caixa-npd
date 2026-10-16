import pandas as pd
import time

def parse_valor(v):
    if pd.isna(v) or v is None:
        return None
    v_str = str(v).strip().replace('.', '').replace(',', '.')
    try:
        return float(v_str)
    except ValueError:
        return v

def parse_data(d):
    if pd.isna(d) or d is None:
        return None
    d_str = str(d).strip()
    try:
        return pd.to_datetime(d_str, format='%d/%m/%Y').date()
    except Exception:
        return d_str

def processar_fluxo_caixa(csv_pagar='contasapagar.csv', csv_receber='contasareceber.csv', excel_saida='FLUXODECAIXA.xlsx'):
    start_time = time.time()
    
    # Mapeamento para coluna Emp -> Empresa
    emp_map = {
        '_001': 'NPD',
        '_002': 'COMPRE',
        '_003': 'DEMO',
        '_004': 'CS'
    }
    
    print(f"Lendo '{csv_pagar}'...")
    df_pagar = pd.read_csv(csv_pagar, encoding='latin1', sep=';', dtype=str)
    
    df_p = pd.DataFrame({
        'Empresa': df_pagar['Emp'].map(emp_map).fillna(df_pagar['Emp']),
        'Movimentação': 'PAGAR',
        'Titular': df_pagar['Fantasia'],
        'Natureza Contábil': df_pagar['Desc_Classe'],
        'Data da Transação': df_pagar['Data Pagto.'].apply(parse_data),
        'Vencimento': df_pagar['Vencimento'].apply(parse_data),
        'Valor': df_pagar['Valor'].apply(parse_valor),
        'Numero': df_pagar['Numero'].str.strip(),
        'Duplicata': pd.NA,
    })
    print(f"  -> {len(df_p)} registros de Contas a Pagar processados.")

    print(f"Lendo '{csv_receber}'...")
    df_receber = pd.read_csv(csv_receber, encoding='latin1', sep=';', dtype=str)
    
    # Regra de Exclusão: Pagamento em branco E Valor_Orig == Valor_Devolvido
    v_orig = df_receber['Valor_Orig'].apply(parse_valor).fillna(0.0)
    v_devol = df_receber['Valor_Devolvido'].apply(parse_valor).fillna(0.0)
    
    pagto_em_branco = (
        df_receber['Pagamento'].isna() |
        (df_receber['Pagamento'].astype(str).str.strip() == '') |
        (df_receber['Pagamento'].astype(str).str.strip() == 'nan')
    )
    devolvido_igual_orig = (v_orig > 0) & (v_orig == v_devol)
    
    filtro_excluir = pagto_em_branco & devolvido_igual_orig
    qtd_excluidos = filtro_excluir.sum()
    
    if qtd_excluidos > 0:
        print(f"  -> Ignorados {qtd_excluidos} registros de Contas a Receber (Pagamento em branco e Valor_Orig == Valor_Devolvido).")
        df_receber = df_receber[~filtro_excluir].copy()

    df_r = pd.DataFrame({
        'Empresa': df_receber['Emp'].map(emp_map).fillna(df_receber['Emp']),
        'Movimentação': 'RECEBER',
        'Titular': df_receber['Nome'],
        'Natureza Contábil': df_receber['Desc_Classe'],
        'Data da Transação': df_receber['Pagamento'].apply(parse_data),
        'Vencimento': df_receber['Vencimento'].apply(parse_data),
        'Valor': df_receber['Valor'].apply(parse_valor),
        'Numero': pd.NA,
        'Duplicata': df_receber['Duplicata'].str.strip(),
    })
    print(f"  -> {len(df_r)} registros de Contas a Receber processados.")

    # Unificar DataFrames (Numero = contas a pagar; Duplicata = contas a receber)
    df_final = pd.concat([df_p, df_r], ignore_index=True)
    total_linhas = len(df_final)
    print(f"Total unificado: {total_linhas} registros.")

    print(f"Gerando arquivo Excel '{excel_saida}' com xlsxwriter...")
    # Garante Numero/Duplicata como texto (preserva zeros à esquerda)
    for col in ('Numero', 'Duplicata'):
        df_final[col] = df_final[col].apply(
            lambda v: None if pd.isna(v) else str(v).strip()
        )

    with pd.ExcelWriter(
        excel_saida,
        engine='xlsxwriter',
        date_format='dd/mm/yyyy',
        engine_kwargs={'options': {'strings_to_numbers': False}},
    ) as writer:
        df_final.to_excel(writer, sheet_name='Fluxo de Caixa', index=False)
        workbook = writer.book
        worksheet = writer.sheets['Fluxo de Caixa']
        text_fmt = workbook.add_format({'num_format': '@'})
        for col_name in ('Numero', 'Duplicata'):
            col_idx = df_final.columns.get_loc(col_name)
            worksheet.set_column(col_idx, col_idx, 18, text_fmt)
            for row_idx, value in enumerate(df_final[col_name], start=1):
                if value is not None and str(value).strip() != '':
                    worksheet.write_string(row_idx, col_idx, str(value), text_fmt)

    elapsed = time.time() - start_time
    print(f"Processamento concluído em {elapsed:.2f} segundos! Arquivo '{excel_saida}' salvo com sucesso.")

if __name__ == '__main__':
    processar_fluxo_caixa()
