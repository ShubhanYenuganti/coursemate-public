# Google Docs-specific content builders for study material export.
# Returns Google Docs API batchUpdate request arrays.
#
# Index tracking note: Google Docs indices are UTF-16 code units. For typical
# study content (ASCII + common Unicode) len(str) ≈ UTF-16 unit count. Emoji
# or surrogate-pair characters would need codepoint-aware counting, but are
# unlikely in flashcard/quiz content.


def _requests_from_segments(segments):
    """
    Build batchUpdate requests from a list of {"text": str, "style": str} dicts.
    Inserts all text at index 1 (start of fresh document), then applies
    updateParagraphStyle for non-normal segments in the same batch.
    Returns list of request dicts.
    """
    normalized = []
    for seg in segments:
        text = seg.get("text") or ""
        if not text.endswith("\n"):
            text += "\n"
        normalized.append({"text": text, "style": seg.get("style", "NORMAL_TEXT")})

    full_text = "".join(s["text"] for s in normalized)
    if not full_text:
        return []

    requests = [
        {
            "insertText": {
                "location": {"index": 1},
                "text": full_text,
            }
        }
    ]

    idx = 1
    for seg in normalized:
        text = seg["text"]
        end_idx = idx + len(text)
        style = seg["style"]
        if style != "NORMAL_TEXT":
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
    Section titles become headings, body text becomes NORMAL_TEXT paragraphs.
    """
    segments = []
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        if i > 0:
            segments.append({"text": "\n", "style": "NORMAL_TEXT"})

        block_type = section.get("type") or section.get("block_type") or "paragraph"
        title = section.get("title") or section.get("heading") or ""
        body = section.get("body") or section.get("content") or ""

        if title:
            if block_type in ("heading_1", "h1"):
                style = "HEADING_1"
            elif block_type in ("heading_3", "h3"):
                style = "HEADING_3"
            else:
                style = "HEADING_2"
            segments.append({"text": title, "style": style})
        elif block_type in ("heading_1", "heading_2", "heading_3") and body:
            # Some report formats encode heading text in the body field
            heading_styles = {"heading_1": "HEADING_1", "heading_2": "HEADING_2", "heading_3": "HEADING_3"}
            segments.append({"text": body, "style": heading_styles[block_type]})
            body = ""

        if body:
            for para in body.split("\n"):
                stripped = para.strip()
                if stripped:
                    segments.append({"text": stripped, "style": "NORMAL_TEXT"})

    return _requests_from_segments(segments)
