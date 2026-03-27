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

    def _s(v) -> str:
        return str(v or "").encode("latin-1", errors="replace").decode("latin-1")

    normalized = normalize_report_sections(report)
    title = _s(normalized.get("title") or "Report")
    subtitle = _s(normalized.get("subtitle") or "")
    sections = normalized.get("sections") or []

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(left=18, top=18, right=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 24)
    pdf.multi_cell(0, 12, txt=title)

    if subtitle:
        pdf.set_font("Helvetica", "", 13)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 8, txt=subtitle)
        pdf.set_text_color(17, 17, 17)

    pdf.ln(6)

    for block in sections:
        btype = block.get("type") or "paragraph"
        content = _s(block.get("content") or "")

        if btype in ("heading", "section"):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 15)
            pdf.multi_cell(0, 9, txt=content)
            pdf.ln(1)

        elif btype in ("subheading", "subsection"):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(0, 7, txt=content)

        elif btype == "paragraph":
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, txt=content)
            pdf.ln(2)

        elif btype in ("bullet_list", "list"):
            pdf.set_font("Helvetica", "", 11)
            for item in (block.get("items") or []):
                pdf.multi_cell(0, 6, txt=f"  - {_s(item)}")
            pdf.ln(2)

        elif btype == "callout":
            pdf.set_font("Helvetica", "I", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.set_x(pdf.get_x() + 5)
            pdf.multi_cell(0, 6, txt=content)
            pdf.set_text_color(17, 17, 17)
            pdf.ln(2)

        elif btype in ("equation", "display_equation"):
            lines = block.get("lines") or ([content] if content else [])
            pdf.set_font("Courier", "", 11)
            for line in lines:
                pdf.multi_cell(0, 6, txt=_s(line))
            pdf.ln(2)

        elif btype == "page_break":
            pdf.add_page()

    return bytes(pdf.output())
