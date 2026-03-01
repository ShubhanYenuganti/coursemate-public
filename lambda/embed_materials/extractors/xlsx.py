"""
Pass 1 extractor for XLSX files using openpyxl.

Each data row becomes one chunk serialized as:
    "SheetName / col1: val | col2: val | ..."

For sheets with > 500 data rows, every 5 rows are batched into a single chunk.
"""
import openpyxl
from io import BytesIO
from typing import List, Dict, Any

ROW_LIMIT = 500
BATCH_SIZE = 5


def _serialize_row(headers: List[str], row: tuple) -> str:
    cells: List[str] = []
    for h, v in zip(headers, row):
        v_str = str(v).strip() if v is not None else ""
        if v_str:
            cells.append(f"{h}: {v_str}" if h else v_str)
    return " | ".join(cells)


def extract_xlsx(file_bytes: bytes) -> List[Dict[str, Any]]:
    wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    chunks: List[Dict[str, Any]] = []

    for sheet in wb.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue

        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        data_rows = rows[1:]
        large = len(data_rows) > ROW_LIMIT

        if large:
            for i in range(0, len(data_rows), BATCH_SIZE):
                batch = data_rows[i : i + BATCH_SIZE]
                parts = [_serialize_row(headers, row) for row in batch]
                parts = [p for p in parts if p]
                if not parts:
                    continue
                row_text = f"{sheet.title} / " + " ; ".join(parts)
                chunks.append({
                    "text": row_text,
                    "chunk_type": "cell",
                    "page_number": None,
                    "token_count": len(row_text.split()),
                })
        else:
            for row in data_rows:
                serialized = _serialize_row(headers, row)
                if not serialized:
                    continue
                row_text = f"{sheet.title} / {serialized}"
                chunks.append({
                    "text": row_text,
                    "chunk_type": "cell",
                    "page_number": None,
                    "token_count": len(row_text.split()),
                })

    wb.close()
    return chunks
