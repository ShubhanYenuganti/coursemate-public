"""
Pass 1 extractor for CSV files using the stdlib csv module.

Every 5 rows are batched into a single chunk serialized as:
    "col1: val | col2: val ; col1: val | col2: val ; ..."
"""
import csv
from io import StringIO
from typing import List, Dict, Any

BATCH_SIZE = 5


def extract_csv(file_bytes: bytes) -> List[Dict[str, Any]]:
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.DictReader(StringIO(text))
    chunks: List[Dict[str, Any]] = []
    batch: List[str] = []

    for row in reader:
        cells: List[str] = []
        for k, v in row.items():
            v_str = str(v).strip() if v else ""
            if v_str:
                cells.append(f"{k}: {v_str}")
        if cells:
            batch.append(" | ".join(cells))

        if len(batch) >= BATCH_SIZE:
            row_text = " ; ".join(batch)
            chunks.append({
                "text": row_text,
                "chunk_type": "cell",
                "page_number": None,
                "token_count": len(row_text.split()),
            })
            batch = []

    if batch:
        row_text = " ; ".join(batch)
        chunks.append({
            "text": row_text,
            "chunk_type": "cell",
            "page_number": None,
            "token_count": len(row_text.split()),
        })

    return chunks
