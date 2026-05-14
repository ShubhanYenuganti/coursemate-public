from dataclasses import dataclass, field


@dataclass
class IndexNode:
    node_id: str
    title: str
    start_page: int
    end_page: int
    summary: str = ""
    nodes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "title": self.title,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "summary": self.summary,
            "nodes": [n.to_dict() for n in self.nodes],
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
