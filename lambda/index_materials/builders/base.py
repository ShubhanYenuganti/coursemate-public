import hashlib
import re
from dataclasses import dataclass, field

STOPWORDS = {
    "about", "after", "also", "and", "are", "because", "been", "between", "both",
    "can", "does", "for", "from", "has", "have", "into", "its", "more", "not",
    "our", "page", "paper", "section", "shows", "such", "that", "the", "their",
    "these", "this", "those", "through", "use", "uses", "using", "was", "were",
    "when", "where", "which", "while", "with",
}

STRUCTURE_FIRST_RETRIEVAL_POLICY = {
    "mode": "structure_first",
    "min_candidate_pages": 2,
    "max_candidate_pages": 4,
    "neighbor_pages": True,
    "prefer_recall": True,
    "use_structure_for": [
        "broad",
        "conceptual",
        "comparative",
        "multi_part",
        "method",
        "result",
        "limitation",
    ],
}


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return value[:48] or "untitled"


def stable_node_id(
    title: str,
    start_page: int,
    end_page: int,
    parent_path: list[str] | None = None,
) -> str:
    path = " > ".join(parent_path or [])
    raw = f"{path}|{title}|{start_page}|{end_page}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"node_{_slug(title)}_{start_page}_{end_page}_{digest}"


def clean_text(text: str) -> str:
    text = re.sub(r"^#{1,6}\s+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def summarize_text(text: str, max_chars: int = 320) -> str:
    cleaned = clean_text(text)
    if len(cleaned) <= max_chars:
        return cleaned
    cutoff = cleaned.rfind(".", 0, max_chars)
    if cutoff < max_chars // 2:
        cutoff = cleaned.rfind(" ", 0, max_chars)
    return cleaned[:cutoff if cutoff > 0 else max_chars].rstrip(" .,") + "."


def keywords_from_text(text: str, limit: int = 10) -> list[str]:
    counts: dict[str, int] = {}
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text.lower()):
        if token in STOPWORDS:
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _count in ranked[:limit]]


@dataclass
class IndexNode:
    node_id: str
    title: str
    start_page: int
    end_page: int
    summary: str = ""
    nodes: list["IndexNode"] = field(default_factory=list)
    node_type: str = "section"
    parent_path: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    source: str = "unknown"
    confidence: float = 1.0
    evidence_pages: list[int] = field(default_factory=list)
    char_start: int | None = None
    char_end: int | None = None

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "title": self.title,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "summary": self.summary,
            "nodes": [n.to_dict() for n in self.nodes],
            "node_type": self.node_type,
            "parent_path": self.parent_path,
            "keywords": self.keywords,
            "source": self.source,
            "confidence": self.confidence,
            "evidence_pages": self.evidence_pages
            or list(range(self.start_page, self.end_page + 1)),
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


@dataclass
class MaterialIndex:
    title: str
    doc_type: str
    page_count: int
    nodes: list = field(default_factory=list)
    retrieval_policy: dict = field(default_factory=lambda: dict(STRUCTURE_FIRST_RETRIEVAL_POLICY))

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "doc_type": self.doc_type,
            "page_count": self.page_count,
            "retrieval_policy": self.retrieval_policy,
            "nodes": [n.to_dict() for n in self.nodes],
        }
