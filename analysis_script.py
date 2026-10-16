import sys
import pandas as pd
import numpy as np
import openpyxl

excel_path = r'c:\dev\FLUXO DE CAIXA\FLUXODECAIXA.xlsx'

print("=== 15. SHEET NAMES ===")
wb = openpyxl.load_workbook(excel_path, read_only=True)
sheet_names = wb.sheetnames
print(f"Sheet names in workbook: {sheet_names}")
wb.close()

xls = pd.ExcelFile(excel_path)
print(f"ExcelFile sheet names: {xls.sheet_names}")

df = pd.read_excel(xls, sheet_name=0)

print("\n" + "="*50)
print(f"ANALYZING SHEET: '{xls.sheet_names[0]}'")
print("="*50)

print("\n=== 1. COLUMN STRUCTURE ===")
print(f"Total Columns: {len(df.columns)}")
for col in df.columns:
    sample_vals = df[col].head(5).tolist()
    print(f"Column: '{col}' | pandas dtype: {df[col].dtype}")
    print(f"  First 5 sample values: {sample_vals}")

print("\n=== 2. ROW COUNTS ===")
total_rows = len(df)
print(f"Total Rows: {total_rows}")
print("Non-null count per column:")
for col in df.columns:
    non_null = df[col].count()
    print(f"  '{col}': {non_null} non-null rows")

print("\n=== 3. NULL/EMPTY ANALYSIS ===")
print("Null count and percentage per column:")
for col in df.columns:
    null_cnt = df[col].isnull().sum()
    null_pct = (null_cnt / total_rows) * 100
    print(f"  '{col}': {null_cnt} nulls ({null_pct:.2f}%)")

def get_col(possible_names):
    for name in possible_names:
        for c in df.columns:
            if c.strip().lower() == name.strip().lower():
                return c
    return None

empresa_col = get_col(['Empresa'])
mov_col = get_col(['Movimentação', 'Movimentacao'])
titular_col = get_col(['Titular'])
natureza_col = get_col(['Natureza Contábil', 'Natureza Contabil'])
dt_trans_col = get_col(['Data da Transação', 'Data da Transacao', 'Data Transação', 'Data Transacao'])
venc_col = get_col(['Vencimento', 'Data Vencimento'])
valor_col = get_col(['Valor'])

print("\n=== 4. COLUMN: Empresa ===")
if empresa_col:
    print(f"Column matched: '{empresa_col}'")
    print(f"Unique values ({df[empresa_col].nunique()}):")
    print(df[empresa_col].value_counts(dropna=False))
else:
    print("Column 'Empresa' not found!")

print("\n=== 5. COLUMN: Movimentação ===")
if mov_col:
    print(f"Column matched: '{mov_col}'")
    print(f"Unique values ({df[mov_col].nunique()}):")
    print(df[mov_col].value_counts(dropna=False))
else:
    print("Column 'Movimentação' not found!")

print("\n=== 6. COLUMN: Titular ===")
if titular_col:
    print(f"Column matched: '{titular_col}'")
    print(f"Unique count: {df[titular_col].nunique()}")
    print(f"Null count: {df[titular_col].isnull().sum()}")
    print("Top 20 most frequent Titular:")
    print(df[titular_col].value_counts(dropna=False).head(20))
else:
    print("Column 'Titular' not found!")

print("\n=== 7. COLUMN: Natureza Contábil ===")
if natureza_col:
    print(f"Column matched: '{natureza_col}'")
    print(f"Unique count: {df[natureza_col].nunique()}")
    print(f"Null count: {df[natureza_col].isnull().sum()}")
    print("Top 30 most frequent Natureza Contábil:")
    print(df[natureza_col].value_counts(dropna=False).head(30))
else:
    print("Column 'Natureza Contábil' not found!")

print("\n=== 8. COLUMN: Data da Transação ===")
if dt_trans_col:
    print(f"Column matched: '{dt_trans_col}'")
    dt_series = pd.to_datetime(df[dt_trans_col], errors='coerce')
    nat_count = dt_series.isnull().sum()
    valid_dt = dt_series.dropna()
    print(f"Min Date: {valid_dt.min()}")
    print(f"Max Date: {valid_dt.max()}")
    print(f"NaT / Invalid Dates Count: {nat_count}")
    print("\nDistribution by Year:")
    print(valid_dt.dt.year.value_counts().sort_index())
    print("\nDistribution by Month (Year-Month):")
    print(valid_dt.dt.to_period('M').value_counts().sort_index())
else:
    print("Column 'Data da Transação' not found!")

print("\n=== 9. COLUMN: Vencimento ===")
if venc_col:
    print(f"Column matched: '{venc_col}'")
    venc_series = pd.to_datetime(df[venc_col], errors='coerce')
    venc_nat_count = venc_series.isnull().sum()
    valid_venc = venc_series.dropna()
    print(f"Min Date: {valid_venc.min()}")
    print(f"Max Date: {valid_venc.max()}")
    print(f"NaT / Invalid Dates Count: {venc_nat_count}")
else:
    print("Column 'Vencimento' not found!")

print("\n=== 10. COLUMN: Valor ===")
if valor_col:
    print(f"Column matched: '{valor_col}'")
    val_series = pd.to_numeric(df[valor_col], errors='coerce')
    null_val = val_series.isnull().sum()
    valid_val = val_series.dropna()
    print(f"Min: {valid_val.min()}")
    print(f"Max: {valid_val.max()}")
    print(f"Mean: {valid_val.mean():.4f}")
    print(f"Median: {valid_val.median():.4f}")
    print(f"Std Dev: {valid_val.std():.4f}")
    print(f"Zero count: {(valid_val == 0).sum()}")
    print(f"Negative count: {(valid_val < 0).sum()}")
    print(f"Positive count: {(valid_val > 0).sum()}")
    print(f"Null count: {null_val}")
    
    print("\nDistribution Histogram (Ranges):")
    bins = [-np.inf, -100000, -10000, -1000, -100, 0, 100, 1000, 10000, 100000, np.inf]
    hist = pd.cut(val_series, bins=bins, include_lowest=True).value_counts().sort_index()
    print(hist)
else:
    print("Column 'Valor' not found!")

print("\n=== 11. DUPLICATE ANALYSIS ===")
exact_dups = df.duplicated().sum()
print(f"Exact Duplicate Rows Count: {exact_dups}")

combo_cols = [c for c in [dt_trans_col, titular_col, valor_col] if c is not None]
if len(combo_cols) == 3:
    combo_dups = df.duplicated(subset=combo_cols, keep=False).sum()
    unique_combo_dups = df.duplicated(subset=combo_cols, keep='first').sum()
    print(f"Duplicate rows on combo ({combo_cols}):")
    print(f"  Total rows participating in duplicates: {combo_dups}")
    print(f"  Extra duplicate rows (keep='first'): {unique_combo_dups}")
else:
    print(f"Could not perform combo duplicate check, found cols: {combo_cols}")

print("\n=== 12. DATE RANGE ===")
if dt_trans_col:
    dt_series = pd.to_datetime(df[dt_trans_col], errors='coerce').dropna()
    if not dt_series.empty:
        print(f"Full Date Range (Data da Transação): {dt_series.min().strftime('%Y-%m-%d')} to {dt_series.max().strftime('%Y-%m-%d')}")
        print(f"Span in days: {(dt_series.max() - dt_series.min()).days} days")

print("\n=== 13. CROSS ANALYSIS: Empresa vs Movimentação ===")
if empresa_col and mov_col:
    ct = pd.crosstab(df[empresa_col], df[mov_col], margins=True, dropna=False)
    print(ct)
else:
    print("Empresa or Movimentação column missing for cross analysis.")

print("\n=== 14. VALUE DISTRIBUTION BY MOVIMENTAÇÃO ===")
if mov_col and valor_col:
    val_series = pd.to_numeric(df[valor_col], errors='coerce')
    for mov_val in df[mov_col].unique():
        sub = val_series[df[mov_col] == mov_val].dropna()
        print(f"\n--- Movimentação: {mov_val} (Count: {len(sub)}) ---")
        print(f"  Min: {sub.min()}")
        print(f"  Max: {sub.max()}")
        print(f"  Mean: {sub.mean():.4f}")
        print(f"  Median: {sub.median():.4f}")
        print(f"  Std Dev: {sub.std():.4f}")
        print(f"  Sum: {sub.sum():.2f}")
        print(f"  Zero count: {(sub == 0).sum()}")
        print(f"  Negative count: {(sub < 0).sum()}")
        print(f"  Positive count: {(sub > 0).sum()}")

print("\n=== END OF REPORT ===")
