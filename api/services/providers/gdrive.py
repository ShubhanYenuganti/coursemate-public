# Google Docs-specific content builders for study material export.
# Returns Google Docs API batchUpdate request arrays.
#
# Index tracking note: Google Docs indices are UTF-16 code units. For typical
# study content (ASCII + common Unicode) len(str) ≈ UTF-16 unit count. Emoji
# or surrogate-pair characters would need codepoint-aware counting, but are
# unlikely in flashcard/quiz content.


def _requests_from_segments(segments):
    """
    Build batchUpdate requests from segments.

    Supported segment shapes:
      - {"text": str, "style": str}
      - {"kind": "page_break"}

    Inserts content sequentially at index 1 (start of fresh document).
    Applies updateParagraphStyle for non-normal text segments.
    Returns list of request dicts.
    """
    normalized = []
    for seg in segments:
        if seg.get("kind") == "page_break":
            normalized.append({"kind": "page_break"})
            continue

        text = seg.get("text") or ""
        if not text:
            continue
        if not text.endswith("\n"):
            text += "\n"
        normalized.append({"kind": "text", "text": text, "style": seg.get("style", "NORMAL_TEXT")})

    if not normalized:
        return []

    requests = []
    idx = 1
    for seg in normalized:
        if seg["kind"] == "page_break":
            requests.append({
                "insertPageBreak": {
                    "location": {"index": idx},
                }
            })
            # Page break is represented as one inserted element.
            idx += 1
            continue

        text = seg["text"]
        style = seg["style"]
        end_idx = idx + len(text)

        requests.append({
            "insertText": {
                "location": {"index": idx},
                "text": text,
            }
        })

        if style != "NORMAL_TEXT" and text.strip():
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": idx, "endIndex": end_idx},
                    "paragraphStyle": {"namedStyleType": style},
                    "fields": "namedStyleType",
                }
            })
        idx = end_idx

    return requests


def flashcard_to_doc_requests(cards):
    """
    Convert flashcard list to Google Docs batchUpdate requests.
    Each card: question as HEADING_3, answer + hint as NORMAL_TEXT.
    """
    segments = []
    for i, card in enumerate(cards):
        if i > 0:
            segments.append({"text": "\n", "style": "NORMAL_TEXT"})
        front = card.get("front") or card.get("question") or ""
        back = card.get("back") or card.get("answer") or ""
        hint = card.get("hint") or ""
        segments.append({"text": f"Q: {front}", "style": "HEADING_3"})
        segments.append({"text": f"A: {back}", "style": "NORMAL_TEXT"})
        if hint:
            segments.append({"text": f"Hint: {hint}", "style": "NORMAL_TEXT"})

    return _requests_from_segments(segments)


def quiz_to_doc_requests(questions):
    """
    Convert quiz question list to Google Docs batchUpdate requests.
    Each question: question text as HEADING_3, options + answer + explanation as NORMAL_TEXT.
    """
    segments = []
    option_labels = "ABCDEFGHIJ"
    for i, q in enumerate(questions):
        if i > 0:
            segments.append({"text": "\n", "style": "NORMAL_TEXT"})
        question_text = q.get("question") or q.get("question_text") or ""
        options = q.get("options") or []
        answer = q.get("answer") or q.get("correct_answer_text") or ""
        explanation = q.get("explanation") or ""

        segments.append({"text": f"{i + 1}. {question_text}", "style": "HEADING_3"})
        for j, opt in enumerate(options):
            label = option_labels[j] if j < len(option_labels) else str(j + 1)
            segments.append({"text": f"({label}) {opt}", "style": "NORMAL_TEXT"})
        if answer:
            segments.append({"text": f"Answer: {answer}", "style": "NORMAL_TEXT"})
        if explanation:
            segments.append({"text": f"Explanation: {explanation}", "style": "NORMAL_TEXT"})

    return _requests_from_segments(segments)


def report_to_doc_requests(sections):
    """
    Convert report sections to Google Docs batchUpdate requests.
    Handles all VALID_BLOCK_TYPES from reports_contracts:
    heading, subheading, paragraph, bullet_list, callout, equation,
    display_equation, table, page_break, list, section, subsection.
    """
    segments = []
    for block in sections:
        if not isinstance(block, dict):
            continue

        btype = str(block.get("type") or block.get("block_type") or "paragraph").lower().strip()
        content = str(block.get("content") or block.get("text") or "").strip()
        lines = block.get("lines")
        if not isinstance(lines, list):
            lines = []
        items = block.get("items")
        if not isinstance(items, list):
            items = []

        if btype in ("heading", "section"):
            if content:
                segments.append({"text": content, "style": "HEADING_2"})

        elif btype in ("subheading", "subsection"):
            if content:
                segments.append({"text": content, "style": "HEADING_3"})

        elif btype in ("equation", "display_equation"):
            # Report contracts emit equation content primarily in `lines`.
            eq_lines = [str(line).strip() for line in lines if str(line).strip()]
            if eq_lines:
                for eq_line in eq_lines:
                    segments.append({"text": eq_line, "style": "NORMAL_TEXT"})
            elif content:
                segments.append({"text": content, "style": "NORMAL_TEXT"})

        elif btype in ("bullet_list", "list"):
            vals = [str(item).strip() for item in items if str(item).strip()]
            if vals:
                for val in vals:
                    segments.append({"text": f"• {val}", "style": "NORMAL_TEXT"})
            elif content:
                segments.append({"text": f"• {content}", "style": "NORMAL_TEXT"})

        elif btype == "callout":
            if content:
                segments.append({"text": f"Note: {content}", "style": "NORMAL_TEXT"})

        elif btype == "table":
            headers = block.get("headers")
            rows = block.get("rows")
            if isinstance(headers, list) and headers:
                header_line = " | ".join(str(h).strip() for h in headers if str(h).strip())
                if header_line:
                    segments.append({"text": header_line, "style": "NORMAL_TEXT"})
            if isinstance(rows, list) and rows:
                for row in rows:
                    if isinstance(row, list):
                        row_line = " | ".join(str(cell).strip() for cell in row if str(cell).strip())
                    else:
                        row_line = str(row).strip()
                    if row_line:
                        segments.append({"text": row_line, "style": "NORMAL_TEXT"})
            elif items:
                for item in items:
                    item_line = str(item).strip()
                    if item_line:
                        segments.append({"text": item_line, "style": "NORMAL_TEXT"})
            elif content:
                segments.append({"text": content, "style": "NORMAL_TEXT"})

        elif btype == "page_break":
            segments.append({"kind": "page_break"})

        else:
            if content:
                segments.append({"text": content, "style": "NORMAL_TEXT"})

    return _requests_from_segments(segments)
