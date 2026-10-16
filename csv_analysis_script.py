import pandas as pd
import numpy as np

pagar_path = r'c:\dev\FLUXO DE CAIXA\contasapagar.csv'
receber_path = r'c:\dev\FLUXO DE CAIXA\contasareceber.csv'

print("==================================================")
print("ANALYSIS OF CONTASAPAGAR.CSV")
print("==================================================")

try:
    df_pagar = pd.read_csv(pagar_path, sep=';', encoding='latin1', low_memory=False)
except Exception as e:
    print("Error loading contasapagar.csv:", e)
    df_pagar = None

if df_pagar is not None:
    print(f"Total Rows: {len(df_pagar)}")
    print("\nColumns and Dtypes:")
    for col in df_pagar.columns:
        print(f"  {col}: {df_pagar[col].dtype}")
    
    print("\nEmp unique values and counts:")
    if 'Emp' in df_pagar.columns:
        print(df_pagar['Emp'].value_counts(dropna=False))
    else:
        print("  'Emp' column not found")
        
    print("\nDesc_Classe unique values count and top 30:")
    if 'Desc_Classe' in df_pagar.columns:
        print(f"Total Unique Desc_Classe: {df_pagar['Desc_Classe'].nunique(dropna=False)}")
        print(df_pagar['Desc_Classe'].value_counts(dropna=False).head(30))
    else:
        print("  'Desc_Classe' column not found")

    print("\nDate range from Vencimento and Data Pagto.:")
    for date_col in ['Vencimento', 'Data Pagto.']:
        if date_col in df_pagar.columns:
            parsed_dates = pd.to_datetime(df_pagar[date_col], format='%d/%m/%Y', errors='coerce')
            print(f"  {date_col}: Min = {parsed_dates.min()}, Max = {parsed_dates.max()}, Nulls = {df_pagar[date_col].isna().sum()}")
        else:
            print(f"  '{date_col}' column not found")

    print("\nValor Pago statistics:")
    if 'Valor Pago' in df_pagar.columns:
        # Convert numeric if string
        val_pago = df_pagar['Valor Pago'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        val_pago_num = pd.to_numeric(val_pago, errors='coerce')
        print(f"  Min: {val_pago_num.min()}")
        print(f"  Max: {val_pago_num.max()}")
        print(f"  Mean: {val_pago_num.mean():.2f}")
        print(f"  Nulls/NaNs: {df_pagar['Valor Pago'].isna().sum()} (unparseable: {val_pago_num.isna().sum()})")
    else:
        print("  'Valor Pago' column not found")

    print("\nFantasia null count:")
    if 'Fantasia' in df_pagar.columns:
        print(f"  Null count: {df_pagar['Fantasia'].isna().sum()} out of {len(df_pagar)}")
    else:
        print("  'Fantasia' column not found")

    print("\nExtra columns distinct counts:")
    extra_cols = ['Nota', 'Credor', 'Nome', 'CNPJ', 'Tipo_Doc', 'Classe', 'Conta_Pagto', 'Banco', 'Situacao']
    for col in extra_cols:
        if col in df_pagar.columns:
            n_unique = df_pagar[col].nunique(dropna=False)
            n_null = df_pagar[col].isna().sum()
            print(f"  {col}: {n_unique} unique values, {n_null} nulls")
        else:
            print(f"  {col}: NOT FOUND in CSV")

    print("\nRows where 'Data Pagto.' is empty but other fields have data:")
    if 'Data Pagto.' in df_pagar.columns:
        empty_pagto = df_pagar[df_pagar['Data Pagto.'].isna() | (df_pagar['Data Pagto.'].astype(str).str.strip() == '')]
        print(f"  Count of rows with empty 'Data Pagto.': {len(empty_pagto)}")
        if len(empty_pagto) > 0:
            print("  Sample empty Data Pagto. rows:")
            print(empty_pagto.head(5)[['Emp', 'Vencimento', 'Data Pagto.', 'Valor Pago'] if set(['Emp', 'Vencimento', 'Data Pagto.', 'Valor Pago']).issubset(df_pagar.columns) else empty_pagto.columns[:5]])
    else:
        print("  'Data Pagto.' column not found")


print("\n==================================================")
print("ANALYSIS OF CONTASARECEBER.CSV")
print("==================================================")

try:
    df_receber = pd.read_csv(receber_path, sep=';', encoding='latin1', low_memory=False)
except Exception as e:
    print("Error loading contasareceber.csv:", e)
    df_receber = None

if df_receber is not None:
    print(f"Total Rows: {len(df_receber)}")
    print("\nColumns and Dtypes:")
    for col in df_receber.columns:
        print(f"  {col}: {df_receber[col].dtype}")
    
    print("\nEmp unique values and counts:")
    if 'Emp' in df_receber.columns:
        print(df_receber['Emp'].value_counts(dropna=False))
    else:
        print("  'Emp' column not found")
        
    print("\nDesc_Classe unique values count and top 30:")
    if 'Desc_Classe' in df_receber.columns:
        print(f"Total Unique Desc_Classe: {df_receber['Desc_Classe'].nunique(dropna=False)}")
        print(df_receber['Desc_Classe'].value_counts(dropna=False).head(30))
    else:
        print("  'Desc_Classe' column not found")

    print("\nDate range from Vencimento and Pagamento:")
    for date_col in ['Vencimento', 'Pagamento']:
        if date_col in df_receber.columns:
            parsed_dates = pd.to_datetime(df_receber[date_col], format='%d/%m/%Y', errors='coerce')
            print(f"  {date_col}: Min = {parsed_dates.min()}, Max = {parsed_dates.max()}, Nulls = {df_receber[date_col].isna().sum()}")
        else:
            print(f"  '{date_col}' column not found")

    print("\nPago statistics:")
    if 'Pago' in df_receber.columns:
        val_pago = df_receber['Pago'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        val_pago_num = pd.to_numeric(val_pago, errors='coerce')
        print(f"  Min: {val_pago_num.min()}")
        print(f"  Max: {val_pago_num.max()}")
        print(f"  Mean: {val_pago_num.mean():.2f}")
        print(f"  Nulls/NaNs: {df_receber['Pago'].isna().sum()} (unparseable: {val_pago_num.isna().sum()})")
    else:
        print("  'Pago' column not found")

    print("\nNome null count:")
    if 'Nome' in df_receber.columns:
        print(f"  Null count: {df_receber['Nome'].isna().sum()} out of {len(df_receber)}")
    else:
        print("  'Nome' column not found")

    print("\nRows where 'Pagamento' is empty:")
    if 'Pagamento' in df_receber.columns:
        empty_pagto = df_receber[df_receber['Pagamento'].isna() | (df_receber['Pagamento'].astype(str).str.strip() == '')]
        print(f"  Count of rows with empty 'Pagamento': {len(empty_pagto)}")
        if len(empty_pagto) > 0:
            print("  Sample empty Pagamento rows:")
            print(empty_pagto.head(5)[['Emp', 'Vencimento', 'Pagamento', 'Pago'] if set(['Emp', 'Vencimento', 'Pagamento', 'Pago']).issubset(df_receber.columns) else empty_pagto.columns[:5]])
    else:
        print("  'Pagamento' column not found")


print("\n==================================================")
print("CROSS-REFERENCE ANALYSIS")
print("==================================================")

if df_pagar is not None and df_receber is not None:
    if 'Desc_Classe' in df_pagar.columns and 'Desc_Classe' in df_receber.columns:
        set_pagar = set(df_pagar['Desc_Classe'].dropna().astype(str).str.strip())
        set_receber = set(df_receber['Desc_Classe'].dropna().astype(str).str.strip())
        common_classes = set_pagar.intersection(set_receber)
        print(f"Desc_Classe in both files count: {len(common_classes)}")
        if len(common_classes) > 0:
            print("Common Desc_Classe values:")
            for c in sorted(common_classes):
                print(f"  - {c}")
    
    if 'Emp' in df_pagar.columns and 'Emp' in df_receber.columns:
        emp_pagar = set(df_pagar['Emp'].dropna().unique())
        emp_receber = set(df_receber['Emp'].dropna().unique())
        print(f"\nEmp in contasapagar: {emp_pagar}")
        print(f"Emp in contasareceber: {emp_receber}")
        print(f"Are Emp values identical sets? {emp_pagar == emp_receber}")
