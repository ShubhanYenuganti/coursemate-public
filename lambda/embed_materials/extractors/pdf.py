"""
Pass 1 extractor for PDF files using PyMuPDF (fitz).

Produces chunks of types: heading, paragraph, table, caption, ocr.

Heading detection: a span whose font size exceeds 1.2× the page average,
or whose bold flag (bit 4 of the flags field) is set.
Caption detection: a block whose maximum font size is below 0.85× the page average.
Embedded images: each raster image on a page is extracted and passed through
Tesseract OCR (via extract_image). Images smaller than MIN_IMAGE_PIXELS are
skipped to avoid wasting time on icons and decorative elements.
"""
import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO
from typing import List, Dict, Any, Set
from .image import extract_image

# Skip images whose total pixel area is below this threshold (icons, logos, etc.)
MIN_IMAGE_PIXELS = 100 * 100  # 10 000 px — ~1 cm² at 100 dpi


def extract_pdf(file_bytes: bytes) -> List[Dict[str, Any]]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    chunks: List[Dict[str, Any]] = []
    seen_xrefs: Set[int] = set()  # deduplicate images reused across pages

    for page_num, page in enumerate(doc, 1):
        blocks = page.get_text("dict")["blocks"]

        # ── collect font sizes to determine page average ──────────────────────
        font_sizes: List[float] = []
        for block in blocks:
            if block.get("type") == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        sz = span.get("size")
                        if sz:
                            font_sizes.append(sz)

        avg_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12.0
        heading_thresh = avg_size * 1.2
        caption_thresh = avg_size * 0.85

        # ── text blocks ───────────────────────────────────────────────────────
        for block in blocks:
            if block.get("type") != 0:
                continue

            line_texts: List[str] = []
            block_max_size: float = 0.0
            block_is_bold = False

            for line in block.get("lines", []):
                line_parts: List[str] = []
                for span in line.get("spans", []):
                    t = span.get("text", "").strip()
                    if t:
                        line_parts.append(t)
                    sz = span.get("size", 12.0)
                    block_max_size = max(block_max_size, sz)
                    if span.get("flags", 0) & (1 << 4):   # bold bit
                        block_is_bold = True
                if line_parts:
                    line_texts.append(" ".join(line_parts))

            text = " ".join(line_texts).strip()
            if not text:
                continue

            if block_max_size > heading_thresh or block_is_bold:
                chunk_type = "heading"
            elif block_max_size < caption_thresh:
                chunk_type = "caption"
            else:
                chunk_type = "paragraph"

            chunks.append({
                "text": text,
                "chunk_type": chunk_type,
                "page_number": page_num,
                "token_count": len(text.split()),
            })

        # ── tables (best-effort) ──────────────────────────────────────────────
        try:
            finder = page.find_tables()
            for table in finder.tables:
                rows = table.extract()
                if not rows:
                    continue
                headers = [str(h).strip() if h else "" for h in rows[0]]
                for row in rows[1:]:
                    cells: List[str] = []
                    for header, val in zip(headers, row):
                        v = str(val).strip() if val is not None else ""
                        if v:
                            cells.append(f"{header}: {v}" if header else v)
                    row_text = " | ".join(cells)
                    if row_text.strip():
                        chunks.append({
                            "text": row_text,
                            "chunk_type": "table",
                            "page_number": page_num,
                            "token_count": len(row_text.split()),
                        })
        except Exception:
            pass  # table extraction is best-effort

        # ── embedded raster images ────────────────────────────────────────────
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            try:
                img_dict  = doc.extract_image(xref)
                img_bytes = img_dict["image"]
                # Guard: skip tiny decorative images
                with Image.open(BytesIO(img_bytes)) as im:
                    w, h = im.size
                if w * h < MIN_IMAGE_PIXELS:
                    continue
                for ocr_chunk in extract_image(img_bytes):
                    ocr_chunk["page_number"] = page_num
                    chunks.append(ocr_chunk)
            except Exception:
                pass  # individual image OCR failure must not abort the page

    doc.close()
    return chunks
