"""Reports PDF builder."""
from __future__ import annotations

from api.services.reports_contracts import normalize_report_sections


def _escape_html(value: object) -> str:
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
    content = _escape_html(block.get("content") or "")

    if block_type in {"heading", "section"}:
        return f"<h2 class='heading'>{content}</h2>"
    if block_type in {"subheading", "subsection"}:
        return f"<h3 class='subheading'>{content}</h3>"
    if block_type == "callout":
        return f"<div class='callout'><p>{content}</p></div>"
    if block_type in {"equation", "display_equation"}:
        lines = block.get("lines") or [block.get("content") or ""]
        line_html = "".join(
            f"<div class='equation-line'>{_escape_html(line)}</div>" for line in lines if str(line or "").strip()
        )
        return f"<div class='equation'>{line_html}</div>"
    if block_type in {"bullet_list", "list"}:
        items = block.get("items") or []
        items_html = "".join(f"<li>{_escape_html(item)}</li>" for item in items)
        return f"<ul class='bullet-list'>{items_html}</ul>"
    if block_type == "page_break":
        page = _escape_html(block.get("page") or "")
        label = f"<span>{page}</span>" if page else ""
        return f"<div class='page-break'>{label}</div>"
    return f"<p class='paragraph'>{content}</p>"


def build_reports_pdf_html(*, report: dict) -> str:
    normalized = normalize_report_sections(report)
    title = _escape_html(normalized.get("title") or "Report")
    subtitle = _escape_html(normalized.get("subtitle") or "")
    date = _escape_html(normalized.get("date") or "")
    sections = normalized.get("sections") or []
    sections_html = "".join(_render_block(section) for section in sections)
    subtitle_html = f"<p class='subtitle'>{subtitle}</p>" if subtitle else ""
    date_html = f"<p class='date'>{date}</p>" if date else ""

    return f"""
    <html>
      <head>
        <meta charset='utf-8' />
        <style>
          @page {{ size: A4; margin: 16mm; }}
          body {{ font-family: sans-serif; color: #111827; }}
          .header {{ text-align: center; margin-bottom: 24px; }}
          h1 {{ font-size: 24px; margin: 0; }}
          .subtitle {{ margin: 8px 0 0 0; color: #4b5563; font-size: 12px; }}
          .date {{ margin: 6px 0 0 0; color: #6b7280; font-size: 11px; }}
          .heading {{ font-size: 16px; margin: 24px 0 10px 0; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb; }}
          .subheading {{ font-size: 14px; margin: 18px 0 8px 0; }}
          .paragraph {{ font-size: 12px; line-height: 1.55; margin: 10px 0; white-space: pre-wrap; }}
          .bullet-list {{ margin: 10px 0 10px 18px; padding: 0; }}
          .bullet-list li {{ margin: 4px 0; font-size: 12px; line-height: 1.45; }}
          .callout {{ margin: 12px 0; padding: 10px 12px; background: #eef2ff; border-left: 4px solid #6366f1; border-radius: 0 8px 8px 0; }}
          .callout p {{ margin: 0; font-size: 12px; color: #3730a3; }}
          .equation {{ margin: 12px 0; padding: 12px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; text-align: center; }}
          .equation-line {{ font-family: monospace; font-size: 12px; }}
          .page-break {{ margin: 24px 0; text-align: center; color: #9ca3af; font-size: 10px; }}
        </style>
      </head>
      <body>
        <div class='header'>
          <h1>{title}</h1>
          {subtitle_html}
          {date_html}
        </div>
        {sections_html}
      </body>
    </html>
    """


def build_reports_pdf_bytes(*, report: dict) -> bytes:
    html = build_reports_pdf_html(report=report)
    try:
        from weasyprint import HTML  # type: ignore
    except Exception:
        return html.encode("utf-8")
    return HTML(string=html).write_pdf()
