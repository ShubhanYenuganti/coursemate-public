# Notion-specific block builders for study material export.
# All functions return plain dicts matching the Notion API block schema.


def rich_text(text: str) -> list:
    """Produce a Notion rich text array from a plain string."""
    return [{"type": "text", "text": {"content": text or ""}}]


def flashcard_to_toggle_block(card: dict) -> dict:
    """
    Convert a flashcard to a Notion toggle block.
    Front becomes the toggle heading; back and hint become paragraph children.
    """
    front = card.get("front") or card.get("question") or ""
    back = card.get("back") or card.get("answer") or ""
    hint = card.get("hint") or ""

    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": rich_text(back)},
        }
    ]
    if hint:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": rich_text(f"Hint: {hint}")},
        })

    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": rich_text(front),
            "children": children,
        },
    }


def quiz_to_blocks(questions: list) -> list:
    """
    Convert a list of quiz question dicts to Notion blocks.
    Each question: heading_2 for the question text, bulleted_list_item per option,
    toggle block revealing the correct answer.
    """
    blocks = []
    for q in questions:
        question_text = q.get("question") or q.get("text") or ""
        options = q.get("options") or []
        answer = str(q.get("answer") or "").strip()
        explanation = str(q.get("explanation") or "").strip()

        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": rich_text(question_text)},
        })

        for opt in options:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": rich_text(str(opt))},
            })

        answer_content = answer
        if explanation:
            answer_content = f"{answer}\n\n{explanation}"

        blocks.append({
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": rich_text("Answer"),
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": rich_text(answer_content)},
                    }
                ],
            },
        })

    return blocks


def report_to_blocks(sections: list) -> list:
    """
    Convert a list of report section dicts to Notion blocks.
    Each section: heading_2 for the section title, paragraphs for content,
    heading_3 for sub-sections.
    """
    blocks = []
    for section in sections:
        title = section.get("title") or section.get("heading") or ""
        content = section.get("content") or section.get("text") or ""
        sub_sections = section.get("sub_sections") or section.get("subsections") or []

        if title:
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": rich_text(title)},
            })

        if content:
            # Split long content into 2000-char paragraph chunks (Notion API limit per rich_text block)
            for chunk in _chunk_text(content, 2000):
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": rich_text(chunk)},
                })

        for sub in sub_sections:
            sub_title = sub.get("title") or sub.get("heading") or ""
            sub_content = sub.get("content") or sub.get("text") or ""
            if sub_title:
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": rich_text(sub_title)},
                })
            if sub_content:
                for chunk in _chunk_text(sub_content, 2000):
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": rich_text(chunk)},
                    })

    return blocks


def _chunk_text(text: str, size: int) -> list:
    """Split text into chunks of at most `size` characters."""
    return [text[i:i + size] for i in range(0, max(len(text), 1), size)]
