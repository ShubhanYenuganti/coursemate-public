import hashlib
import re
from dataclasses import dataclass, field


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

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "doc_type": self.doc_type,
            "page_count": self.page_count,
            "nodes": [n.to_dict() for n in self.nodes],
        }
