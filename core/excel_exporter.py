import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

COLUMNS = [
    "File name", "Carrier", "Shipper", "Consignee", "Notify party 1",
    "POL", "Vessel name", "Voyage number", "POD", "Place of delivery",
    "Cont no.", "Seal no.", "Total carton", "Cont type",
    "Total GW", "Total CBM", "ATD", "Description"
]

def export_to_excel(all_data, output_path):
    df = pd.DataFrame(all_data, columns=COLUMNS)

    writer = pd.ExcelWriter(output_path, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name='ONE Bills')

    wb = writer.book
    ws = writer.sheets['ONE Bills']

    # Header styling
    header_font  = Font(bold=True, color="FFFFFF", size=11)
    header_fill  = PatternFill(start_color="1565C0", end_color="1565C0", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for cell in ws[1]:
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = header_align

    ws.row_dimensions[1].height = 30

    # Body: wrap text cho các ô dài
    # Căn lề trên (Top) cho tất cả các ô để dễ đọc khi bị merge
    for row in ws.iter_rows(min_row=2, max_row=len(df)+1, min_col=1, max_col=len(COLUMNS)):
        for cell in row:
            cell.alignment = Alignment(vertical='top', horizontal='left', wrap_text=True)

    # ==========================================
    # Logic Gộp ô (Merge Cells) cho các cột chung
    # ==========================================
    # Danh sách các cột KHÔNG gộp (cột riêng của từng container)
    container_cols = ["Cont no.", "Seal no.", "Total carton", "Cont type", "Total GW", "Total CBM"]
    merge_col_indices = [COLUMNS.index(col) + 1 for col in COLUMNS if col not in container_cols]
    
    start_row = 2
    for i in range(1, len(df)):
        if df.iloc[i]["File name"] != df.iloc[i-1]["File name"]:
            end_row = i + 1
            if end_row > start_row:
                for col_idx in merge_col_indices:
                    ws.merge_cells(start_row=start_row, start_column=col_idx, end_row=end_row, end_column=col_idx)
            start_row = i + 2
            
    # Gộp group cuối cùng
    end_row = len(df) + 1
    if end_row > start_row:
        for col_idx in merge_col_indices:
            ws.merge_cells(start_row=start_row, start_column=col_idx, end_row=end_row, end_column=col_idx)

    # Auto column width (max 50)
    for col_cells in ws.columns:
        max_len = max(
            (len(str(c.value)) for c in col_cells if c.value is not None),
            default=10
        )
        ws.column_dimensions[get_column_letter(col_cells[0].column)].width = min(max_len + 2, 50)

    writer.close()
