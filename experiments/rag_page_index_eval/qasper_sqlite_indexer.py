from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

from .qasper_loader import load_qasper_huggingface, load_qasper_json
from .sqlite_store import (
    connect,
    init_schema,
    store_material_relation,
    store_course_index,
    store_page_index,
    store_page_texts,
    upsert_material_map,
)
from .types import PageRecord, QueryExample


BUILDERS_ROOT = Path(__file__).resolve().parents[2] / "lambda" / "index_materials"
if str(BUILDERS_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILDERS_ROOT))

from builders.document import build_from_pages
from llm_client import (
    RELATION_CONFIDENCE_THRESHOLD,
    build_doc_summary_prompt,
    build_metadata_tags_prompt,
    build_node_keywords_prompt,
    build_node_summary_prompt,
    build_relations_prompt,
    extract_keywords,
    extract_tags,
    summarize,
)


def _call_with_retries(label: str, fn, *args, retries: int = 3, **kwargs):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt >= retries:
                break
            delay = min(2 ** attempt, 10)
            print(
                f"  {label} failed on attempt {attempt}/{retries}: {exc}; retrying in {delay}s",
                flush=True,
            )
            time.sleep(delay)
    raise last_exc


def _resolve_section_names(page_rows: list[dict], material_index) -> list[dict]:
    routing_node_types = {"section", "slide", "problem", "solution", "question"}

    def _walk(nodes, page_num: int, ancestors: list[str] | None = None) -> tuple[str, list[str]] | None:
        ancestors = ancestors or []
        for node in nodes:
            if node.start_page <= page_num <= node.end_page:
                node_type = getattr(node, "node_type", "section")
                if node_type in routing_node_types:
                    path = (node.parent_path or ancestors) + [node.title]
                    current = (node.title, path)
                else:
                    path = node.parent_path or ancestors
                    current = (path[-1], path) if path else None
                child_hit = _walk(node.nodes, page_num, path)
                return child_hit if child_hit else current
        return None

    result = []
    for row in page_rows:
        section = _walk(material_index.nodes, row["page_number"])
        if section:
            section_name, section_path = section
        else:
            section_name, section_path = None, []
        result.append({**row, "section_name": section_name, "section_path": section_path})
    return result


def _paper_titles(queries: list[QueryExample]) -> dict[str, str]:
    titles: dict[str, str] = {}
    for query in queries:
        title = query.metadata.get("title")
        if title and query.paper_id not in titles:
            titles[query.paper_id] = str(title)
    return titles


def _paper_pages(pages: list[PageRecord]) -> dict[str, list[PageRecord]]:
    grouped: dict[str, list[PageRecord]] = defaultdict(list)
    for page in pages:
        grouped[page.paper_id].append(page)
    return {
        paper_id: sorted(items, key=lambda page: page.page_number)
        for paper_id, items in grouped.items()
    }


def _doc_summary(title: str, pages: list[PageRecord]) -> str:
    sections = [page.section_name for page in pages if page.section_name]
    section_text = ", ".join(dict.fromkeys(sections[:8]))
    return f"QASPER academic paper. Title: {title}. Sections: {section_text}".strip()


def _metadata_tags(pages: list[PageRecord], limit: int = 12) -> list[str]:
    counts: dict[str, int] = {}
    for page in pages:
        text = f"{page.section_name or ''} {page.text or ''}".lower()
        for raw in text.replace("-", " ").split():
            token = "".join(ch for ch in raw if ch.isalnum())
            if len(token) < 5 or token in {"section", "paper", "using", "their", "these", "which"}:
                continue
            counts[token] = counts.get(token, 0) + 1
    return [token for token, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _node_page_text(node, page_rows: dict[int, dict]) -> str:
    texts = []
    for page_num in range(node.start_page, node.end_page + 1):
        row = page_rows.get(page_num)
        if row and row.get("text_content"):
            texts.append(row["text_content"])
    return "\n\n".join(texts)


def _walk_nodes(nodes):
    for node in nodes:
        yield node
        yield from _walk_nodes(node.nodes)


def _fallback_keywords(title: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", title.lower())
    return [word for word in words if word not in {"and", "for", "from", "into", "the", "this", "with"}][:15]


def _enrich_material_index(material_index, page_rows: dict[int, dict], doc_type: str, api_key: str) -> dict:
    stats = {"node_summary_calls": 0, "node_keyword_calls": 0}
    nodes = list(_walk_nodes(material_index.nodes))
    total = len(nodes)
    for idx, node in enumerate(nodes, start=1):
        text = _node_page_text(node, page_rows).strip()
        if text:
            node.summary = _call_with_retries(
                "node summary",
                summarize,
                build_node_summary_prompt(doc_type, text),
                api_key,
            )
            stats["node_summary_calls"] += 1
        keywords_text = text or node.title
        keywords = _call_with_retries(
            "node keywords",
            extract_keywords,
            build_node_keywords_prompt(doc_type, keywords_text),
            api_key,
        )
        node.keywords = keywords[:15] if keywords else _fallback_keywords(node.title)
        stats["node_keyword_calls"] += 1
        if total > 10 and (idx == 1 or idx % 10 == 0 or idx == total):
            print(
                f"  enrich nodes {idx}/{total} for current material; "
                f"llm_calls={stats['node_summary_calls'] + stats['node_keyword_calls']}",
                flush=True,
            )
    return stats


def _extract_json_array(raw: str) -> list[dict]:
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        value = json.loads(match.group(0))
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _build_sqlite_relations(conn, course_id: int, api_key: str, progress_every: int) -> int:
    rows = [
        dict(row)
        for row in conn.execute(
            """SELECT material_id, material_title, doc_type, material_summary, metadata_tags
               FROM course_material_index
               WHERE course_id = ?
               ORDER BY material_id""",
            (course_id,),
        ).fetchall()
    ]
    for row in rows:
        row["metadata_tags"] = json.loads(row.get("metadata_tags") or "[]")

    stored = 0
    started = time.time()
    total = len(rows)
    for idx, target in enumerate(rows, start=1):
        others = [row for row in rows if row["material_id"] != target["material_id"]]
        if not others:
            continue
        raw = _call_with_retries(
            "relations",
            summarize,
            build_relations_prompt(target, others),
            api_key,
        )
        for rel in _extract_json_array(raw):
            if rel.get("relation_type") not in {"prerequisite", "extends", "practice_for", "solution_for"}:
                continue
            confidence = float(rel.get("confidence", 0) or 0)
            if confidence < RELATION_CONFIDENCE_THRESHOLD:
                continue
            store_material_relation(
                conn,
                course_id=course_id,
                source_id=int(rel["source_id"]),
                target_id=int(rel["target_id"]),
                relation_type=rel["relation_type"],
                shared_tags=rel.get("shared_tags", []),
                similarity_score=confidence,
            )
            stored += 1
        if progress_every > 0 and (idx == 1 or idx % progress_every == 0 or idx == total):
            elapsed = time.time() - started
            rate = idx / elapsed if elapsed > 0 else 0
            remaining = (total - idx) / rate if rate > 0 else 0
            print(
                "relation progress "
                f"{idx}/{total} materials ({idx / total:.1%}); "
                f"stored={stored}; elapsed={elapsed:.1f}s eta={remaining:.1f}s",
                flush=True,
            )
    return stored


def index_qasper_to_sqlite(
    *,
    qasper_json: Path | None,
    dataset_source: str = "json",
    hf_dataset: str = "allenai/qasper",
    split: str = "test",
    sqlite_db: Path,
    course_id: int = 1,
    limit_papers: int | None = None,
    paper_order: str = "paper_id",
    progress_every: int = 25,
    index_mode: str = "llm_enriched",
    openai_key: str | None = None,
    build_relations: bool = True,
    resume: bool = True,
) -> dict:
    started = time.time()
    if dataset_source == "json":
        if qasper_json is None:
            raise ValueError("--qasper-json is required when --dataset-source=json")
        pages, queries = load_qasper_json(qasper_json)
    elif dataset_source == "huggingface":
        pages, queries = load_qasper_huggingface(hf_dataset, split)
    else:
        raise ValueError(f"Unsupported dataset source: {dataset_source}")
    titles = _paper_titles(queries)
    grouped_pages = _paper_pages(pages)
    if paper_order == "paper_id":
        paper_ids = sorted(grouped_pages)
    elif paper_order == "source":
        seen = []
        for page in pages:
            if page.paper_id not in seen:
                seen.append(page.paper_id)
        paper_ids = seen
    else:
        raise ValueError(f"Unsupported paper order: {paper_order}")
    if limit_papers:
        paper_ids = paper_ids[:limit_papers]
    api_key = openai_key or os.environ.get("OPENAI_API_KEY_INDEXER")
    if index_mode == "llm_enriched" and not api_key:
        raise ValueError("OPENAI_API_KEY_INDEXER or --openai-key is required for --index-mode llm_enriched")
    if index_mode not in {"llm_enriched", "deterministic"}:
        raise ValueError(f"Unsupported index mode: {index_mode}")

    sqlite_db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(sqlite_db)
    llm_calls = 0
    relations_stored = 0
    try:
        init_schema(conn)
        total = len(paper_ids)
        existing_material_ids = set()
        if resume:
            existing_material_ids = {
                int(row[0])
                for row in conn.execute(
                    "SELECT material_id FROM material_page_index"
                ).fetchall()
            }
        for material_id, paper_id in enumerate(paper_ids, start=1):
            if material_id in existing_material_ids:
                if progress_every > 0 and (
                    material_id == 1 or material_id % progress_every == 0 or material_id == total
                ):
                    elapsed = time.time() - started
                    print(
                        "index progress "
                        f"{material_id}/{total} materials "
                        f"({material_id / total:.1%}); skipped existing; "
                        f"elapsed={elapsed:.1f}s llm_calls={llm_calls}",
                        flush=True,
                    )
                continue
            paper_pages = grouped_pages[paper_id]
            title = titles.get(paper_id, paper_id)
            material_index = build_from_pages(
                [page.text for page in paper_pages],
                doc_type="academic_paper",
                title=title,
                headings_override=[
                    (page.page_number - 1, page.section_name or f"Evidence location {page.page_number}")
                    for page in paper_pages
                ],
            )
            page_rows = [
                {
                    "page_number": page.page_number,
                    "text_content": page.text,
                    "has_images": False,
                    "section_name": page.section_name,
                    "section_path": list(page.section_path),
                }
                for page in paper_pages
            ]
            page_rows = _resolve_section_names(page_rows, material_index)
            page_rows_by_number = {row["page_number"]: row for row in page_rows}
            if index_mode == "llm_enriched":
                enrich_stats = _enrich_material_index(
                    material_index,
                    page_rows_by_number,
                    "academic_paper",
                    api_key,
                )
                llm_calls += enrich_stats["node_summary_calls"] + enrich_stats["node_keyword_calls"]
                node_titles = [node.title for node in material_index.nodes]
                doc_summary = _call_with_retries(
                    "doc summary",
                    summarize,
                    build_doc_summary_prompt(title, "academic_paper", node_titles),
                    api_key,
                )
                llm_calls += 1
                metadata_tags = _call_with_retries(
                    "metadata tags",
                    extract_tags,
                    build_metadata_tags_prompt(title, "academic_paper", doc_summary, node_titles),
                    api_key,
                )
                llm_calls += 1
            else:
                doc_summary = _doc_summary(title, paper_pages)
                metadata_tags = _metadata_tags(paper_pages)
            upsert_material_map(
                conn,
                paper_id=paper_id,
                material_id=material_id,
                course_id=course_id,
                title=title,
            )
            store_page_texts(conn, material_id, page_rows)
            store_page_index(conn, material_id, material_index.to_dict())
            store_course_index(
                conn,
                material_id=material_id,
                course_id=course_id,
                material_title=title,
                doc_type="academic_paper",
                page_count=len(paper_pages),
                summary=doc_summary,
                metadata_tags=metadata_tags,
            )
            if progress_every > 0 and (
                material_id == 1 or material_id % progress_every == 0 or material_id == total
            ):
                elapsed = time.time() - started
                rate = material_id / elapsed if elapsed > 0 else 0
                remaining = (total - material_id) / rate if rate > 0 else 0
                print(
                    "index progress "
                    f"{material_id}/{total} materials "
                    f"({material_id / total:.1%}); "
                    f"elapsed={elapsed:.1f}s eta={remaining:.1f}s llm_calls={llm_calls}",
                    flush=True,
                )
        if index_mode == "llm_enriched" and build_relations:
            relations_stored = _build_sqlite_relations(conn, course_id, api_key, progress_every)
            llm_calls += len(paper_ids)
        conn.commit()
    finally:
        conn.close()

    return {
        "sqlite_db": str(sqlite_db),
        "course_id": course_id,
        "materials_indexed": len(paper_ids),
        "pages_indexed": sum(len(grouped_pages[paper_id]) for paper_id in paper_ids),
        "llm_calls": llm_calls,
        "relations_stored": relations_stored,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Index QASPER into a production-shaped SQLite PageIndex store.")
    parser.add_argument("--dataset-source", choices=["json", "huggingface"], default="json")
    parser.add_argument("--qasper-json")
    parser.add_argument("--hf-dataset", default="allenai/qasper")
    parser.add_argument("--split", default="test", choices=["train", "validation", "test"])
    parser.add_argument("--sqlite-db", required=True)
    parser.add_argument("--course-id", type=int, default=1)
    parser.add_argument("--limit-papers", type=int)
    parser.add_argument(
        "--paper-order",
        choices=["paper_id", "source"],
        default="paper_id",
        help="Deterministic paper selection order used before applying --limit-papers.",
    )
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--index-mode", choices=["llm_enriched", "deterministic"], default="llm_enriched")
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY_INDEXER"))
    parser.add_argument("--skip-relations", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    result = index_qasper_to_sqlite(
        qasper_json=Path(args.qasper_json) if args.qasper_json else None,
        dataset_source=args.dataset_source,
        hf_dataset=args.hf_dataset,
        split=args.split,
        sqlite_db=Path(args.sqlite_db),
        course_id=args.course_id,
        limit_papers=args.limit_papers,
        paper_order=args.paper_order,
        progress_every=args.progress_every,
        index_mode=args.index_mode,
        openai_key=args.openai_key,
        build_relations=not args.skip_relations,
        resume=not args.no_resume,
    )
    print(
        "indexed "
        f"{result['materials_indexed']} materials, "
        f"{result['pages_indexed']} evidence locations, "
        f"{result['relations_stored']} relations, "
        f"{result['llm_calls']} llm calls into {result['sqlite_db']}"
    )


if __name__ == "__main__":
    main()
