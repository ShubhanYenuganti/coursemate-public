from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from .types import PageRecord, QueryExample


BUILDERS_ROOT = Path(__file__).resolve().parents[2] / "lambda" / "index_materials"
if str(BUILDERS_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILDERS_ROOT))

from builders.document import build_from_pages


def _parse_pages(pages_str: str) -> list[int]:
    result: list[int] = []
    for part in (pages_str or "").split(","):
        part = part.strip()
        match = re.match(r"^(\d+)-(\d+)$", part)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            result.extend(range(start, end + 1))
        elif re.match(r"^\d+$", part):
            result.append(int(part))
    return result


class QasperPageIndexAdapter:
    """In-memory implementation of the production pageindex retrieval API."""

    def __init__(self, pages: list[PageRecord], queries: list[QueryExample]):
        self.pages = list(pages)
        self.queries = list(queries)
        self.paper_titles = self._paper_titles(queries)
        self.paper_to_material_id: dict[str, int] = {}
        self.material_id_to_paper: dict[int, str] = {}
        for paper_id in sorted({page.paper_id for page in self.pages}):
            material_id = len(self.paper_to_material_id) + 1
            self.paper_to_material_id[paper_id] = material_id
            self.material_id_to_paper[material_id] = paper_id
        self.material_indexes = {
            material_id: build_from_pages(
                [page.text for page in self._pages_for_material(material_id)],
                doc_type="academic_paper",
                title=self.paper_titles.get(paper_id, paper_id),
                headings_override=[
                    (page.page_number - 1, page.section_name or f"Evidence location {page.page_number}")
                    for page in self._pages_for_material(material_id)
                ],
            )
            for material_id, paper_id in self.material_id_to_paper.items()
        }

    @staticmethod
    def _paper_titles(queries: list[QueryExample]) -> dict[str, str]:
        titles: dict[str, str] = {}
        for query in queries:
            title = query.metadata.get("title")
            if title and query.paper_id not in titles:
                titles[query.paper_id] = str(title)
        return titles

    def _pages_for_material(self, material_id: int) -> list[PageRecord]:
        paper_id = self.material_id_to_paper.get(material_id)
        return sorted(
            [page for page in self.pages if page.paper_id == paper_id],
            key=lambda page: page.page_number,
        )

    def _page_summary(self, page: PageRecord) -> str:
        text = " ".join((page.text or "").split())
        prefix = f"{page.section_name}: " if page.section_name else ""
        return (prefix + text)[:240]

    def _routing_sections(self, material_id: int) -> list[dict]:
        material_index = self.material_indexes[material_id]
        sections: list[dict] = []

        def walk(nodes: list[dict]) -> None:
            for node in nodes:
                keywords = ", ".join(node.get("keywords") or [])
                summary = node.get("summary") or ""
                if keywords:
                    summary = f"{summary} keywords: {keywords}".strip()
                sections.append(
                    {
                        "start_page": node["start_page"],
                        "end_page": node["end_page"],
                        "summary": f"{node['title']}: {summary}"[:320],
                    }
                )
                walk(node.get("nodes") or [])

        walk(material_index.to_dict()["nodes"])
        return sections

    def get_course_routing_index(
        self,
        conn,
        course_id: int,
        material_ids: list[int] | None = None,
    ) -> list[dict]:
        selected_ids = material_ids or sorted(self.material_id_to_paper)
        rows = []
        for material_id in selected_ids:
            paper_id = self.material_id_to_paper.get(material_id)
            if not paper_id:
                continue
            pages = self._pages_for_material(material_id)
            rows.append(
                {
                    "material_id": material_id,
                    "title": self.paper_titles.get(paper_id, paper_id),
                    "doc_type": "academic_paper",
                    "page_count": len(pages),
                    "summary": "QASPER paper indexed with the CourseMate document builder.",
                    "tags": ["qasper", "academic-paper"],
                    "sections": self._routing_sections(material_id),
                }
            )
        return rows

    def get_material_structure(self, conn, material_id: int) -> dict:
        paper_id = self.material_id_to_paper.get(material_id)
        if not paper_id:
            return {"error": f"No index found for material {material_id}."}
        return {
            "material_id": material_id,
            "paper_id": paper_id,
            "nodes": self.material_indexes[material_id].to_dict()["nodes"],
        }

    def get_page_content(self, conn, material_id: int, pages: str) -> list[dict]:
        requested = set(_parse_pages(pages))
        if not requested:
            return []
        return [
            {
                "page_number": page.page_number,
                "text_content": page.text,
                "has_images": False,
            }
            for page in self._pages_for_material(material_id)
            if page.page_number in requested
        ]

    def get_material_relations(self, conn, course_id: int, material_id: int) -> list[dict]:
        return []

    @contextmanager
    def patch_production_pageindex(self) -> Iterator[None]:
        with (
            patch("pageindex_retrieval.get_course_routing_index", self.get_course_routing_index),
            patch("pageindex_retrieval.get_material_structure", self.get_material_structure),
            patch("pageindex_retrieval.get_page_content", self.get_page_content),
            patch("pageindex_retrieval.get_material_relations", self.get_material_relations),
        ):
            yield


def fetched_locations_from_tool_trace(
    tool_trace: list[dict],
    adapter: QasperPageIndexAdapter,
    limit: int,
) -> list[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    locations: list[tuple[str, int]] = []
    for trace in tool_trace:
        if trace.get("tool") != "get_page_content":
            continue
        args = trace.get("args") or {}
        paper_id = adapter.material_id_to_paper.get(args.get("material_id"))
        if not paper_id:
            continue
        for page_number in _parse_pages(str(args.get("pages", ""))):
            location = (paper_id, page_number)
            if location in seen:
                continue
            seen.add(location)
            locations.append(location)
            if len(locations) >= limit:
                return locations
    return locations
