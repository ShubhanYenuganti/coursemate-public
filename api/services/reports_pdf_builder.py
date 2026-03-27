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
            f"<div class=\"equation-line\">\\[{_e(line)}\\]</div>"
            for line in lines
            if str(line or "").strip()
        )
        return f"<div class=\"equation\">{equation_html}</div>"
    if block_type == "table":
        headers = block.get("headers") or []
        rows = block.get("rows") or []
        header_html = ""
        if headers:
            cells = "".join(f"<th>{_e(h)}</th>" for h in headers)
            header_html = f"<thead><tr>{cells}</tr></thead>"
        body_html = "".join(
            "<tr>" + "".join(f"<td>{_e(cell)}</td>" for cell in row) + "</tr>"
            for row in rows
        )
        return f"<table>{header_html}<tbody>{body_html}</tbody></table>"
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
    <title>{title}</title>
    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"
    />
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
      table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
      th, td {{ border: 1px solid #ccc; padding: 6px 8px; font-size: 12px; text-align: left; }}
      th {{ background: #f0f0f0; font-weight: bold; }}
      .equation-line {{ margin: 6px 0; }}
    </style>
    <script
      defer
      src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"
    ></script>
    <script
      defer
      src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
    ></script>
  </head>
  <body>
    <h1>{title}</h1>
    {subtitle_html}
    {blocks}
  </body>
</html>
"""


def build_reports_pdf_bytes(*, report: dict) -> bytes:
    import os
    from fpdf import FPDF  # type: ignore

    _FONTS = os.path.join(os.path.dirname(__file__), "fonts")

    normalized = normalize_report_sections(report)
    title = normalized.get("title") or "Report"
    subtitle = normalized.get("subtitle") or ""
    sections = normalized.get("sections") or []

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_font("DejaVu", "", os.path.join(_FONTS, "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", os.path.join(_FONTS, "DejaVuSans-Bold.ttf"))
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()
    W = pdf.w - pdf.l_margin - pdf.r_margin

    def mc(h, text):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(W, h, str(text or ""), align="L")

    pdf.set_font("DejaVu", "B", 24)
    mc(12, title)

    if subtitle:
        pdf.set_font("DejaVu", "", 13)
        pdf.set_text_color(80, 80, 80)
        mc(8, subtitle)
        pdf.set_text_color(17, 17, 17)

    pdf.ln(6)

    for block in sections:
        btype = block.get("type") or "paragraph"
        content = str(block.get("content") or "")

        if btype in {"heading", "section"}:
            pdf.ln(4)
            pdf.set_font("DejaVu", "B", 15)
            mc(9, content)
            pdf.ln(1)

        elif btype in {"subheading", "subsection"}:
            pdf.ln(2)
            pdf.set_font("DejaVu", "B", 12)
            mc(7, content)

        elif btype == "paragraph":
            pdf.set_font("DejaVu", "", 11)
            mc(6, content)
            pdf.ln(2)

        elif btype in {"bullet_list", "list"}:
            pdf.set_font("DejaVu", "", 11)
            for item in (block.get("items") or []):
                mc(6, f"  \u2022 {item}")
            pdf.ln(2)

        elif btype == "callout":
            pdf.set_font("DejaVu", "", 11)
            pdf.set_text_color(60, 60, 60)
            mc(6, content)
            pdf.set_text_color(17, 17, 17)
            pdf.ln(2)

        elif btype in {"equation", "display_equation"}:
            lines = block.get("lines") or ([content] if content else [])
            pdf.set_font("DejaVu", "", 11)
            for line in lines:
                mc(6, line)
            pdf.ln(2)

        elif btype == "table":
            headers = block.get("headers") or []
            rows = block.get("rows") or []
            n_cols = len(headers) or (len(rows[0]) if rows else 0)
            if n_cols:
                col_w = W / n_cols
                pdf.set_font("DejaVu", "B", 10)
                if headers:
                    x0, y0 = pdf.l_margin, pdf.get_y()
                    for i, h in enumerate(headers):
                        pdf.set_xy(x0 + i * col_w, y0)
                        pdf.multi_cell(col_w, 6, str(h or ""), border=1, align="L")
                    pdf.set_xy(x0, pdf.get_y())
                pdf.set_font("DejaVu", "", 10)
                for row in rows:
                    x0, y0 = pdf.l_margin, pdf.get_y()
                    for i, cell in enumerate(row[:n_cols]):
                        pdf.set_xy(x0 + i * col_w, y0)
                        pdf.multi_cell(col_w, 6, str(cell or ""), border=1, align="L")
                    pdf.set_xy(x0, pdf.get_y())
                pdf.ln(3)

        elif btype == "page_break":
            pdf.add_page()

    return bytes(pdf.output())
