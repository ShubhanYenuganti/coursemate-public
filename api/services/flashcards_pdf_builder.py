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
    from fpdf import FPDF  # type: ignore

    def _s(v) -> str:
        return str(v or "").encode("latin-1", errors="replace").decode("latin-1")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(left=18, top=18, right=18)

    cards = deck.get("cards") or []

    # --- Cover page ---
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 22)
    pdf.multi_cell(0, 10, txt=_s(deck.get("title") or "Flashcards"))

    topic = _s(deck.get("topic") or "")
    if topic:
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 7, txt=topic)
        pdf.set_text_color(17, 17, 17)

    pdf.ln(4)

    model_str = f"{_s(deck.get('provider') or '')} {_s(deck.get('model_id') or '')}".strip()
    if model_str:
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 7, txt=f"Model: {model_str}")

    depth = _s(deck.get("depth") or "moderate")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, txt=f"Mode: {depth.title()}")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 6, txt=f"{len(cards)} card{'s' if len(cards) != 1 else ''}")

    gen_at = _s(deck.get("generated_at") or "")
    if gen_at:
        pdf.multi_cell(0, 6, txt=f"Generated: {gen_at}")
    pdf.set_text_color(17, 17, 17)

    # --- Cards ---
    pdf.add_page()

    for card in cards:
        idx = card.get("card_index")
        front = _s(card.get("front") or "")
        back = _s(card.get("back") or "")
        hint = _s(card.get("hint") or "")

        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(79, 70, 229)
        pdf.multi_cell(0, 7, txt=f"Card {idx}")
        pdf.set_text_color(17, 17, 17)

        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(0, 6, txt="Front:")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, txt=front)
        pdf.ln(1)

        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(0, 6, txt="Back:")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, txt=back)

        if hint:
            pdf.ln(1)
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(0, 5, txt=f"Hint: {hint}")
            pdf.set_text_color(17, 17, 17)

        pdf.ln(5)

    return bytes(pdf.output())
