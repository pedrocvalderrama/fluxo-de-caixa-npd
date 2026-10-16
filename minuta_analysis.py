import openpyxl
import os

file_path = r'c:\dev\FLUXO DE CAIXA\Minuta Fluxo de Caixa.xlsx'

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    exit(1)

wb = openpyxl.load_workbook(file_path, data_only=False)
wb_data = openpyxl.load_workbook(file_path, data_only=True)

print(f"=== WORKBOOK ANALYSIS: {file_path} ===")
print(f"Sheet names: {wb.sheetnames}\n")

for sheet_name in wb.sheetnames:
    ws = wb[sheet_name]
    ws_data = wb_data[sheet_name]
    
    print(f"=========================================")
    print(f"SHEET: {sheet_name}")
    print(f"Dimensions: {ws.dimensions} (Max row: {ws.max_row}, Max col: {ws.max_column})")
    
    # Merged cells
    if ws.merged_cells:
        print(f"\n--- Merged Cells ({len(ws.merged_cells.ranges)}) ---")
        for mrange in ws.merged_cells.ranges:
            print(f"  Merged range: {mrange.coord}")
    else:
        print("\nNo merged cells.")

    # Headers and Rows
    print("\n--- Row Content ---")
    formulas_found = []
    
    for r in range(1, ws.max_row + 1):
        row_vals = []
        row_eval_vals = []
        has_content = False
        for c in range(1, ws.max_column + 1):
            cell = ws.cell(row=r, column=c)
            cell_data = ws_data.cell(row=r, column=c)
            
            val = cell.value
            eval_val = cell_data.value
            
            if val is not None:
                has_content = True
                if isinstance(val, str) and val.startswith('='):
                    formulas_found.append((cell.coordinate, val, eval_val))
            
            row_vals.append(val)
            row_eval_vals.append(eval_val)
            
        if has_content:
            row_repr = [str(v) if v is not None else "" for v in row_vals]
            # Trim trailing empty strings for printing brevity
            while row_repr and row_repr[-1] == "":
                row_repr.pop()
            print(f"Row {r:2d}: {row_repr}")
            
    if formulas_found:
        print(f"\n--- Formulas Found ({len(formulas_found)}) ---")
        for coord, formula, eval_val in formulas_found:
            print(f"  Cell {coord}: Formula='{formula}' | Evaluated Value='{eval_val}'")
    else:
        print("\nNo formulas found in this sheet.")

    print("\n")
