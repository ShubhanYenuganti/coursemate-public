"""Reports PDF builder."""
from __future__ import annotations

from api.services.reports_contracts import normalize_report_sections


def _e(value: object) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _render_block(block: dict) -> str:
    block_type = str(block.get("type") or "paragraph")
    content = _e(block.get("content") or "")

    if block_type in {"heading", "section"}:
        return f"<h2>{content}</h2>"
    if block_type in {"subheading", "subsection"}:
        return f"<h3>{content}</h3>"
    if block_type == "callout":
        return f"<div class=\"callout\">{content}</div>"
    if block_type in {"bullet_list", "list"}:
        items = block.get("items") or []
        items_html = "".join(f"<li>{_e(item)}</li>" for item in items)
        return f"<ul>{items_html}</ul>"
    if block_type in {"equation", "display_equation"}:
        lines = block.get("lines") or [block.get("content") or ""]
        equation_html = "".join(
            f"<div class=\"equation-line\">{_e(line)}</div>"
            for line in lines
            if str(line or "").strip()
        )
        return f"<div class=\"equation\">{equation_html}</div>"
    if block_type == "page_break":
        return '<div class="page-break"></div>'
    return f"<p>{content}</p>"


def build_reports_pdf_html(*, report: dict) -> str:
    normalized = normalize_report_sections(report)
    title = _e(normalized.get("title") or "Report")
    subtitle = _e(normalized.get("subtitle") or "")
    blocks = "".join(_render_block(block) for block in normalized.get("sections") or [])
    subtitle_html = f"<p class=\"subtitle\">{subtitle}</p>" if subtitle else ""

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>
      @page {{ size: A4; margin: 16mm; }}
      body {{ font-family: Arial, sans-serif; color: #111; }}
      h1 {{ margin: 0 0 8px; font-size: 24px; }}
      h2 {{ margin: 24px 0 8px; font-size: 18px; }}
      h3 {{ margin: 18px 0 6px; font-size: 15px; }}
      p {{ margin: 10px 0; line-height: 1.5; }}
      ul {{ margin: 10px 0 10px 20px; }}
      li {{ margin: 4px 0; }}
      .subtitle {{ margin: 0 0 20px; color: #555; }}
      .callout {{ background: #f5f5f5; border-left: 4px solid #999; padding: 12px; margin: 12px 0; }}
      .page-break {{ page-break-after: always; border-top: 1px dashed #ccc; margin: 32px 0; }}
    </style>
  </head>
  <body>
    <h1>{title}</h1>
    {subtitle_html}
    {blocks}
  </body>
</html>
"""


def build_reports_pdf_bytes(*, report: dict) -> bytes:
    from fpdf import FPDF  # type: ignore

    _TYPO = str.maketrans({
        '\u2014': '--',  '\u2013': '-',   '\u2012': '-',   '\u2015': '--',
        '\u2018': "'",   '\u2019': "'",   '\u201a': "'",
        '\u201c': '"',   '\u201d': '"',   '\u201e': '"',
        '\u2026': '...', '\u00a0': ' ',   '\u2022': '-',
        '\u2010': '-',   '\u2011': '-',   '\u25cf': '-',
    })

    def _s(v) -> str:
        return str(v or "").translate(_TYPO).encode("latin-1", errors="replace").decode("latin-1")

    normalized = normalize_report_sections(report)
    title = _s(normalized.get("title") or "Report")
    subtitle = _s(normalized.get("subtitle") or "")
    sections = normalized.get("sections") or []

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()
    W = pdf.w - pdf.l_margin - pdf.r_margin  # ~174mm for A4 w/ 18mm margins

    def mc(h, text):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(W, h, _s(text), align="L")

    pdf.set_font("Helvetica", "B", 24)
    mc(12, title)

    if subtitle:
        pdf.set_font("Helvetica", "", 13)
        pdf.set_text_color(80, 80, 80)
        mc(8, subtitle)
        pdf.set_text_color(17, 17, 17)

    pdf.ln(6)

    for block in sections:
        btype = block.get("type") or "paragraph"
        content = _s(block.get("content") or "")

        if btype == "heading":
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 15)
            mc(9, content)
            pdf.ln(1)

        elif btype == "subheading":
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 12)
            mc(7, content)

        elif btype == "paragraph":
            pdf.set_font("Helvetica", "", 11)
            mc(6, content)
            pdf.ln(2)

        elif btype == "bullet_list":
            pdf.set_font("Helvetica", "", 11)
            for item in (block.get("items") or []):
                mc(6, f"  - {_s(item)}")
            pdf.ln(2)

        elif btype == "callout":
            pdf.set_font("Helvetica", "I", 11)
            pdf.set_text_color(60, 60, 60)
            mc(6, content)
            pdf.set_text_color(17, 17, 17)
            pdf.ln(2)

        elif btype == "equation":
            lines = block.get("lines") or ([content] if content else [])
            pdf.set_font("Courier", "", 11)
            for line in lines:
                mc(6, line)
            pdf.ln(2)

        elif btype == "table":
            headers = block.get("headers") or []
            rows = block.get("rows") or []
            n_cols = len(headers) or (len(rows[0]) if rows else 0)
            if n_cols:
                col_w = W / n_cols
                # Measure the tallest cell in each row so all cells in a row share the same height
                def _row_height(cells, font_style, font_size, line_h):
                    pdf.set_font("Helvetica", font_style, font_size)
                    max_lines = 1
                    for cell_text in cells:
                        text = _s(cell_text)
                        # Estimate number of lines by splitting on width
                        char_w = pdf.get_string_width("W") or 1
                        estimated = max(1, int(len(text) * char_w / col_w) + 1)
                        max_lines = max(max_lines, estimated)
                    return line_h * max_lines

                if headers:
                    row_h = _row_height(headers, "B", 10, 6)
                    pdf.set_font("Helvetica", "B", 10)
                    x0 = pdf.l_margin
                    y0 = pdf.get_y()
                    for i, h in enumerate(headers):
                        pdf.set_xy(x0 + i * col_w, y0)
                        pdf.multi_cell(col_w, 6, _s(h), border=1, align="L")
                    pdf.set_xy(x0, y0 + row_h)

                pdf.set_font("Helvetica", "", 10)
                for row in rows:
                    cells = row[:n_cols]
                    row_h = _row_height(cells, "", 10, 6)
                    x0 = pdf.l_margin
                    y0 = pdf.get_y()
                    for i, cell_text in enumerate(cells):
                        pdf.set_xy(x0 + i * col_w, y0)
                        pdf.multi_cell(col_w, 6, _s(cell_text), border=1, align="L")
                    pdf.set_xy(x0, y0 + row_h)
                pdf.ln(3)

        elif btype == "page_break":
            pdf.add_page()

    return bytes(pdf.output())
