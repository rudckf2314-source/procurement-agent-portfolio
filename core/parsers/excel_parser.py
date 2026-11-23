from __future__ import annotations
from openpyxl import load_workbook
import io

def excel_to_text(file_bytes: bytes) -> str:
    wb = load_workbook(filename=io.BytesIO(file_bytes), data_only=True)
    chunks = []
    
    # Process all sheets
    for ws in wb.worksheets:
        chunks.append(f"[SHEET] {ws.title}")
        
        # Increase limit to capture more data, but keep a safety cap
        max_row = min(ws.max_row, 2000)
        max_col = min(ws.max_column, 50)
        
        for r in range(1, max_row + 1):
            row_vals = []
            for c in range(1, max_col + 1):
                v = ws.cell(r, c).value
                if v is None:
                    continue
                s = str(v).strip()
                if s:
                    row_vals.append(s)
            
            # Only add non-empty rows
            if row_vals:
                chunks.append(" | ".join(row_vals))
                
    return "\n".join(chunks)

