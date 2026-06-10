from __future__ import annotations

from itertools import groupby

from .types import IndexNodeRecord, PageRecord


def build_index_records(paper_id: str, pages: list[PageRecord]) -> list[IndexNodeRecord]:
    records = []
    ordered = sorted(
        [page for page in pages if page.paper_id == paper_id],
        key=lambda page: page.page_number,
    )

    for section_name, group in groupby(ordered, key=lambda page: page.section_name or "Unknown"):
        section_pages = list(group)
        start = section_pages[0].page_number
        end = section_pages[-1].page_number
        text = " ".join(page.text for page in section_pages)
        words = text.split()
        summary = " ".join(words[:80])
        keywords = tuple(sorted({word.lower().strip(".,:;()[]") for word in words if len(word) > 5})[:20])
        records.append(
            IndexNodeRecord(
                paper_id=paper_id,
                node_id=f"{paper_id}:{section_name}:{start}-{end}",
                title=section_name,
                start_page=start,
                end_page=end,
                summary=summary,
                node_type="section",
                parent_path=(section_name,),
                keywords=keywords,
            )
        )

    return records
