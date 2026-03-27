"""
Quiz PDF builder for Phase 2.

Uses weasyprint to convert simple HTML into a PDF.
"""

from __future__ import annotations

from datetime import datetime


def _escape_html(value: str) -> str:
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def build_quiz_pdf_html(*, quiz: dict) -> str:
    """
    quiz keys (expected):
      - title, topic, provider, model_id, generated_at
      - generation_settings (optional)
      - questions: [{question_index, type, question, options?, answer}]
    """
    title = _escape_html(str(quiz.get("title") or "Quiz"))
    topic = _escape_html(str(quiz.get("topic") or ""))
    provider = _escape_html(str(quiz.get("provider") or ""))
    model_id = _escape_html(str(quiz.get("model_id") or ""))
    generated_at = _escape_html(str(quiz.get("generated_at") or ""))

    generation_settings = quiz.get("generation_settings") or {}
    counts = generation_settings.get("counts") or {}
    counts_text = (
        f"TF: {counts.get('tf', 0)}, SA: {counts.get('sa', 0)}, LA: {counts.get('la', 0)}, MCQ: {counts.get('mcq', 0)}"
        if counts
        else ""
    )

    questions = quiz.get("questions") or []

    def render_question(q, show_answer: bool):
        q_idx = q.get("question_index")
        q_type = _escape_html(str(q.get("type") or ""))
        q_text = _escape_html(str(q.get("question") or ""))
        options = q.get("options") or []
        answer = _escape_html(str(q.get("answer") or ""))

        options_html = ""
        if options and isinstance(options, list):
            options_html = "<ul>" + "".join(f"<li>{_escape_html(str(o))}</li>" for o in options) + "</ul>"

        answer_html = f"<p><b>Answer:</b> {answer}</p>" if show_answer else ""

        return f"""
            <div class="qblock">
              <div class="qhdr">
                <span class="qidx">{q_idx}.</span>
                <span class="qtype">{q_type}</span>
              </div>
              <div class="qtext">{q_text}</div>
              {options_html}
              {answer_html}
            </div>
        """

    questions_pages = []
    # We keep it simple: one question per "section". For many questions we still paginate via CSS.
    for q in questions:
        questions_pages.append(render_question(q, show_answer=False))

    answer_key_blocks = [render_question(q, show_answer=True) for q in questions]

    questions_html = "".join(questions_pages)
    answer_key_html = "".join(answer_key_blocks)

    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          @page {{ size: A4; margin: 18mm; }}
          body {{ font-family: sans-serif; color: #111; }}
          .cover {{ page-break-after: always; }}
          .subtitle {{ color: #444; font-size: 12px; margin-top: 6px; }}
          .meta {{ margin-top: 14px; font-size: 12px; color: #333; }}
          .section-title {{ font-size: 14px; font-weight: 700; margin: 0 0 10px 0; }}
          .qblock {{ margin: 10px 0 18px 0; padding-bottom: 10px; border-bottom: 1px solid #eee; }}
          .qhdr {{ display: flex; gap: 8px; align-items: baseline; }}
          .qidx {{ font-weight: 700; }}
          .qtype {{ font-size: 12px; color: #555; text-transform: uppercase; }}
          .qtext {{ margin: 6px 0; font-size: 12.5px; line-height: 1.3; white-space: pre-wrap; }}
          ul {{ margin: 6px 0 0 18px; }}
          .answer-key {{ page-break-before: always; }}
          .answer-key .section-title {{ margin-bottom: 6px; }}
          .generated-at {{ font-size: 12px; color: #333; margin-top: 6px; }}
        </style>
      </head>
      <body>
        <div class="cover">
          <h1 style="margin:0; font-size:22px;">{title}</h1>
          <div class="subtitle">{topic}</div>
          <div class="meta">
            <div><b>Model:</b> {provider} {model_id}</div>
            {f"<div>{counts_text}</div>" if counts_text else ""}
            <div class="generated-at"><b>Generated:</b> {generated_at}</div>
          </div>
          <div style="margin-top:22px; font-size:12px; color:#444;">
            This quiz was generated from the selected course materials.
          </div>
        </div>

        <div class="questions">
          <div class="section-title">Quiz</div>
          {questions_html}
        </div>

        <div class="answer-key">
          <div class="section-title">Answer Key</div>
          {answer_key_html}
        </div>
      </body>
    </html>
    """
    return html


def build_quiz_pdf_bytes(*, quiz: dict) -> bytes:
    from fpdf import FPDF  # type: ignore

    def _s(v) -> str:
        return str(v or "").encode("latin-1", errors="replace").decode("latin-1")

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()
    W = pdf.w - pdf.l_margin - pdf.r_margin  # ~174mm for A4 w/ 18mm margins

    def mc(h, text):
        pdf.multi_cell(W, h, _s(text))

    # --- Cover page ---
    pdf.set_font("Helvetica", "B", 22)
    mc(10, quiz.get("title") or "Quiz")

    topic = _s(quiz.get("topic") or "")
    if topic:
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(80, 80, 80)
        mc(7, topic)
        pdf.set_text_color(17, 17, 17)

    pdf.ln(4)

    model_str = f"{_s(quiz.get('provider') or '')} {_s(quiz.get('model_id') or '')}".strip()
    if model_str:
        pdf.set_font("Helvetica", "", 11)
        mc(7, f"Model: {model_str}")

    gen_at = _s(quiz.get("generated_at") or "")
    if gen_at:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(80, 80, 80)
        mc(6, f"Generated: {gen_at}")
        pdf.set_text_color(17, 17, 17)

    counts = (quiz.get("generation_settings") or {}).get("counts") or {}
    if counts:
        parts = [f"{k.upper()}: {v}" for k, v in counts.items() if v]
        if parts:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(80, 80, 80)
            mc(6, ", ".join(parts))
            pdf.set_text_color(17, 17, 17)

    # --- Questions ---
    questions = quiz.get("questions") or []

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    mc(9, "Quiz")
    pdf.ln(2)

    for q in questions:
        q_type = _s(q.get("type") or "").upper()
        q_text = _s(q.get("question") or "")
        options = q.get("options") or []

        pdf.set_font("Helvetica", "B", 11)
        header = f"{q.get('question_index')}.  [{q_type}]" if q_type else f"{q.get('question_index')}."
        mc(7, header)
        pdf.set_font("Helvetica", "", 11)
        mc(6, q_text)

        for i, opt in enumerate(options):
            pdf.set_font("Helvetica", "", 10)
            mc(5, f"  {chr(65 + i)}. {_s(opt)}")

        pdf.ln(3)

    # --- Answer key ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    mc(9, "Answer Key")
    pdf.ln(2)

    for q in questions:
        q_type = _s(q.get("type") or "").upper()
        q_text = _s(q.get("question") or "")
        answer = _s(q.get("answer") or "")

        pdf.set_font("Helvetica", "B", 11)
        header = f"{q.get('question_index')}.  [{q_type}]" if q_type else f"{q.get('question_index')}."
        mc(7, header)
        pdf.set_font("Helvetica", "", 11)
        mc(6, q_text)

        if answer:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(0, 100, 0)
            mc(6, f"Answer: {answer}")
            pdf.set_text_color(17, 17, 17)

        pdf.ln(3)

    return bytes(pdf.output())

