"""Flashcards PDF builder."""

from __future__ import annotations


def _escape_html(value: str) -> str:
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def build_flashcards_pdf_html(*, deck: dict) -> str:
    title = _escape_html(str(deck.get('title') or 'Flashcards'))
    topic = _escape_html(str(deck.get('topic') or ''))
    provider = _escape_html(str(deck.get('provider') or ''))
    model_id = _escape_html(str(deck.get('model_id') or ''))
    generated_at = _escape_html(str(deck.get('generated_at') or ''))
    cards = deck.get('cards') or []

    rows_html = []
    for card in cards:
        idx = card.get('card_index')
        front = _escape_html(str(card.get('front') or ''))
        back = _escape_html(str(card.get('back') or ''))
        hint = _escape_html(str(card.get('hint') or ''))
        hint_line = f"<div class='hint'><b>Hint:</b> {hint}</div>" if hint else ""
        rows_html.append(
            f"""
            <div class='card'>
              <div class='idx'>Card {idx}</div>
              <div class='front'><b>Front:</b> {front}</div>
              <div class='back'><b>Back:</b> {back}</div>
              {hint_line}
            </div>
            """
        )

    cards_html = ''.join(rows_html)

    return f"""
    <html>
      <head>
        <meta charset='utf-8' />
        <style>
          @page {{ size: A4; margin: 16mm; }}
          body {{ font-family: sans-serif; color: #111; }}
          .meta {{ margin: 10px 0 18px 0; font-size: 12px; color: #333; }}
          .card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px; margin: 0 0 10px 0; page-break-inside: avoid; }}
          .idx {{ font-size: 11px; color: #4b5563; margin-bottom: 6px; font-weight: 700; }}
          .front, .back {{ font-size: 12px; line-height: 1.4; white-space: pre-wrap; margin-bottom: 6px; }}
          .hint {{ font-size: 11px; color: #4b5563; }}
        </style>
      </head>
      <body>
        <h1 style='margin:0; font-size:22px;'>{title}</h1>
        <div style='margin-top:6px; color:#4b5563; font-size:12px;'>{topic}</div>
        <div class='meta'>
          <div><b>Model:</b> {provider} {model_id}</div>
          <div><b>Generated:</b> {generated_at}</div>
        </div>
        {cards_html}
      </body>
    </html>
    """


def build_flashcards_pdf_bytes(*, deck: dict) -> bytes:
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as e:
        raise RuntimeError(f"weasyprint is not available: {e}")

    html = build_flashcards_pdf_html(deck=deck)
    return HTML(string=html).write_pdf()
