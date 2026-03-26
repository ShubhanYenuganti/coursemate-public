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
    html = build_reports_pdf_html(report=report)
    try:
        from weasyprint import HTML  # type: ignore
    except ImportError:
        return html.encode("utf-8")
    return HTML(string=html).write_pdf()
