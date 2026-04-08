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
    Convert a flat list of typed report block dicts to Notion blocks.
    Handles all VALID_BLOCK_TYPES: heading, subheading, paragraph, bullet_list,
    callout, equation, display_equation, table, page_break, list, section, subsection.
    """
    blocks = []
    for block in sections:
        btype = str(block.get("type") or "paragraph").lower().strip()
        content = str(block.get("content") or block.get("text") or "").strip()
        items = block.get("items") or block.get("lines") or []
        if not isinstance(items, list):
            items = []

        if btype in ("heading", "section"):
            if content:
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": rich_text(content)},
                })

        elif btype in ("subheading", "subsection"):
            if content:
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": rich_text(content)},
                })

        elif btype in ("equation", "display_equation"):
            # LLM emits LaTeX in a `lines` array; fall back to `content` if absent.
            # Join multiple lines with a newline so multi-line expressions render correctly.
            lines_val = block.get("lines")
            if isinstance(lines_val, list) and lines_val:
                expr = "\n".join(str(l) for l in lines_val if str(l).strip())
            else:
                expr = content
            if expr:
                blocks.append({
                    "object": "block",
                    "type": "equation",
                    "equation": {"expression": expr},
                })

        elif btype in ("bullet_list", "list"):
            for item in items:
                item_str = str(item).strip()
                if not item_str:
                    continue
                for chunk in _chunk_text(item_str, 2000):
                    blocks.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": rich_text(chunk)},
                    })
            # If no items but content exists, fall back to a paragraph.
            if not items and content:
                for chunk in _chunk_text(content, 2000):
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": rich_text(chunk)},
                    })

        elif btype == "callout":
            if content:
                blocks.append({
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": rich_text(content),
                        "icon": {"type": "emoji", "emoji": "💡"},
                        "color": "default",
                    },
                })

        elif btype == "table":
            # Notion tables require pre-structured rows. The LLM emits unstructured
            # data, so render items as bulleted rows; fall back to paragraph.
            if items:
                for item in items:
                    item_str = str(item).strip()
                    if item_str:
                        blocks.append({
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {"rich_text": rich_text(item_str)},
                        })
            elif content:
                for chunk in _chunk_text(content, 2000):
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": rich_text(chunk)},
                    })

        elif btype == "page_break":
            # Notion has no page_break; use a divider as the closest equivalent.
            blocks.append({
                "object": "block",
                "type": "divider",
                "divider": {},
            })

        else:
            # paragraph (default) — split into 2000-char chunks per Notion API limit.
            if content:
                for chunk in _chunk_text(content, 2000):
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": rich_text(chunk)},
                    })

    return blocks


def _chunk_text(text: str, size: int) -> list:
    """Split text into chunks of at most `size` characters."""
    return [text[i:i + size] for i in range(0, max(len(text), 1), size)]
