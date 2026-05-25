import os
import re
import requests

_URL = "https://api.openai.com/v1/chat/completions"
_MODEL = "gpt-4o-mini"
_TIMEOUT = 30

_NODE_SUMMARY_PROMPTS = {
    "lecture_slide": (
        "Summarize this lecture slide section in at most 120 tokens. "
        "Focus on the key concept, theorem, or equation being taught. "
        "Be concise and precise."
    ),
    "lecture_note": (
        "Summarize this lecture note section in at most 120 tokens. "
        "Focus on the key concept or argument being made."
    ),
    "hw_instruction": (
        "Summarize this homework problem section in at most 120 tokens. "
        "Identify the concept being tested and what the student must do."
    ),
    "hw_solution": (
        "Summarize this homework solution section in at most 120 tokens. "
        "Identify the problem being solved and the approach used."
    ),
    "reading": (
        "Summarize this reading section in at most 120 tokens. "
        "Focus on the main argument or finding."
    ),
    "discussion_note": (
        "Summarize this discussion section in at most 120 tokens. "
        "Focus on the key topic or question discussed."
    ),
    "quiz": (
        "Summarize this quiz question in at most 120 tokens. "
        "Identify the concept being assessed."
    ),
    "exam": (
        "Summarize this exam question in at most 120 tokens. "
        "Identify the concept being assessed."
    ),
}

_DEFAULT_NODE_PROMPT = (
    "Summarize this document section in at most 120 tokens. "
    "Focus on the main concept or topic covered."
)

_DOC_SUMMARY_PROMPT = (
    "Write a 2-3 sentence summary of this course document. "
    "Mention the document type, main topics covered, and what a student would learn from it."
)

_TAGS_PROMPT = (
    "Extract 5-15 concise topic/concept tags from this course material. "
    "Tags must be lowercase, hyphenated noun phrases "
    "(e.g. 'backpropagation', 'chain-rule', 'gradient-descent'). "
    "Focus on specific technical concepts. "
    "Output only a JSON array of strings, nothing else. "
    "Example: [\"backpropagation\", \"chain-rule\"]\n\n"
)

_RELATIONS_SYSTEM = (
    "You identify semantic relationships between course materials.\n"
    "Allowed relation types:\n"
    "prerequisite       — existing material must be understood before the target\n"
    "extends            — target directly builds on concepts in existing material\n"
    "practice_for       — target (hw/quiz/exam) tests concepts taught in existing material (lecture)\n"
    "solution_for       — target is a solution set for an existing hw/exam"
)

RELATION_CONFIDENCE_THRESHOLD = 0.6


def build_node_summary_prompt(doc_type: str, section_text: str) -> str:
    system_instruction = _NODE_SUMMARY_PROMPTS.get(doc_type, _DEFAULT_NODE_PROMPT)
    return f"{system_instruction}\n\nContent:\n{section_text[:2000]}"


def build_node_keywords_prompt(doc_type: str, section_text: str) -> str:
    return (
        f"Extract 5 to 15 retrieval keywords for this {doc_type} section. "
        "Return only a JSON array of short strings. Include methods, datasets, "
        "metrics, named entities, formulas, and key concepts when present.\n\n"
        f"{section_text[:6000]}"
    )


def build_doc_summary_prompt(title: str, doc_type: str, node_titles: list[str]) -> str:
    sections = ", ".join(node_titles[:15])
    return (
        f"{_DOC_SUMMARY_PROMPT}\n\n"
        f"Document title: {title}\n"
        f"Document type: {doc_type}\n"
        f"Sections/topics covered: {sections}"
    )


def build_metadata_tags_prompt(title: str, doc_type: str, summary: str, node_titles: list[str]) -> str:
    sections = ", ".join(node_titles[:20])
    return (
        f"{_TAGS_PROMPT}"
        f"Title: {title}\nType: {doc_type}\nSummary: {summary}\nSections: {sections}"
    )


def build_relations_prompt(target: dict, others: list[dict]) -> str:
    def fmt(m: dict) -> str:
        tags = ", ".join(m.get("metadata_tags") or [])
        return (
            f"ID: {m['material_id']} | Title: {m['material_title']} | Type: {m['doc_type']}\n"
            f"  Summary: {m.get('material_summary', '')[:200]}\n"
            f"  Tags: {tags}"
        )

    target_str = fmt(target)
    others_str = "\n\n".join(fmt(o) for o in others)

    return (
        f"{_RELATIONS_SYSTEM}\n\n"
        f"TARGET material (newly indexed):\n{target_str}\n\n"
        f"EXISTING course materials:\n{others_str}\n\n"
        "Identify relationships between the TARGET and EXISTING materials.\n"
        "Use source_id for the conceptually earlier material, target_id for the dependent one.\n"
        'Format: [{"source_id": int, "target_id": int, "relation_type": str, '
        '"shared_tags": [str], "confidence": float}]\n'
        "If no confident relationships exist, output: []"
    )


def summarize(prompt: str, api_key: str) -> str:
    resp = requests.post(
        _URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150,
            "temperature": 0.0,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def get_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY_INDEXER")
    if not key:
        raise ValueError("OPENAI_API_KEY_INDEXER env var not set")
    return key


def extract_tags(prompt: str, api_key: str) -> list[str]:
    raw = summarize(prompt, api_key)
    m = re.search(r'\[.*?\]', raw, re.DOTALL)
    if not m:
        return []
    try:
        import json as _json
        tags = _json.loads(m.group(0))
        return [str(t).strip().lower() for t in tags if t]
    except Exception:
        return []


def extract_keywords(prompt: str, api_key: str) -> list[str]:
    return extract_tags(prompt, api_key)


def describe_visuals(png_b64: str, api_key: str) -> str:
    """Send a page image to gpt-4o-mini and return the raw JSON string response."""
    prompt_text = (
        "Analyze this course material page. "
        "Return ONLY a JSON object with these exact fields:\n"
        "{\n"
        '  "visual_summary": "<description of all visual content in at most 120 tokens>",\n'
        '  "detected_figures": [{"label": "<Figure N or short label>", "description": "<what it shows>"}],\n'
        '  "detected_tables": [{"label": "<Table N or short label>", "description": "<what it contains>"}]\n'
        "}\n"
        "Use empty arrays when there are no figures or tables. Output JSON only — no other text."
    )
    resp = requests.post(
        _URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png_b64}"}},
                    ],
                }
            ],
            "max_tokens": 400,
            "temperature": 0.0,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()
