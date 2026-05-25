from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

from .agentic_adapter import QasperPageIndexAdapter, fetched_locations_from_tool_trace
from .metrics import evaluate_hits
from .qasper_loader import load_qasper_json
from .types import MetricResult, QueryExample, RetrievalHit


API_DIR = Path(__file__).resolve().parents[2] / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def evaluate_agentic_result(
    query: QueryExample,
    fetched_locations: list[tuple[str, int]],
    k: int,
) -> MetricResult:
    hits = [
        RetrievalHit(
            paper_id=paper_id,
            unit_id=f"{paper_id}:{page_number}",
            unit_type="agent_fetched_location",
            score=1.0 / rank,
            pages={page_number},
            text="",
        )
        for rank, (paper_id, page_number) in enumerate(fetched_locations[:k], start=1)
    ]
    return evaluate_hits(query, hits, "agentic_pageindex", k)


def serialize_tool_trace(tool_trace: list[dict]) -> str:
    return json.dumps(tool_trace, separators=(",", ":"), ensure_ascii=False)


def _averages(rows: list[dict]) -> dict[str, float]:
    metrics = [
        "recall_at_k",
        "mrr_at_k",
        "ndcg_at_k",
        "evidence_location_hit_at_k",
        "answerability_coverage",
        "tool_call_count",
        "fetched_location_count",
        "latency_ms",
    ]
    return {
        metric: sum(float(row[metric]) for row in rows) / len(rows)
        for metric in metrics
    }


def _write_summary(path: Path, rows: list[dict], k: int) -> None:
    averages = _averages(rows)
    lines = [
        "# Agentic PageIndex QASPER Eval",
        "",
        "## Metrics",
        "",
        f"| Variant | Recall@{k} | MRR@{k} | NDCG@{k} | Evidence Location Hit@{k} | Answerability Coverage | Tool Calls | Fetched Locations | Avg Latency ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            "| agentic_pageindex | "
            f"{averages['recall_at_k']:.3f} | "
            f"{averages['mrr_at_k']:.3f} | "
            f"{averages['ndcg_at_k']:.3f} | "
            f"{averages['evidence_location_hit_at_k']:.3f} | "
            f"{averages['answerability_coverage']:.3f} | "
            f"{averages['tool_call_count']:.2f} | "
            f"{averages['fetched_location_count']:.2f} | "
            f"{averages['latency_ms']:.0f} |"
        ),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_agentic_eval(
    qasper_json: Path,
    out: Path,
    openai_key: str,
    model: str,
    k: int = 5,
    limit: int | None = None,
    summary_out: Path | None = None,
    progress_every: int = 10,
) -> list[dict]:
    from llm import run_agent_pageindex

    pages, queries = load_qasper_json(qasper_json)
    adapter = QasperPageIndexAdapter(pages, queries)
    selected_queries = queries[:limit] if limit else queries
    rows: list[dict] = []
    fieldnames = [
        "query_id",
        "variant",
        "recall_at_k",
        "mrr_at_k",
        "ndcg_at_k",
        "evidence_location_hit_at_k",
        "answerability_coverage",
        "paper_id",
        "question",
        "tool_call_count",
        "fetched_location_count",
        "latency_ms",
        "tool_trace_json",
        "answer",
    ]

    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        with adapter.patch_production_pageindex():
            total = len(selected_queries)
            for idx, query in enumerate(selected_queries, start=1):
                material_id = adapter.paper_to_material_id[query.paper_id]
                started = time.time()
                answer, _grounding_refs, tool_trace, *_ = run_agent_pageindex(
                    conn=None,
                    user_message=query.question,
                    model=model,
                    api_key=openai_key,
                    chat_id=None,
                    course_id=1,
                    context_material_ids=[material_id],
                )
                fetched_locations = fetched_locations_from_tool_trace(tool_trace, adapter, limit=k)
                result = evaluate_agentic_result(query, fetched_locations, k)
                row = result.__dict__ | {
                    "paper_id": query.paper_id,
                    "question": query.question,
                    "tool_call_count": sum(1 for entry in tool_trace if "tool" in entry),
                    "fetched_location_count": len(fetched_locations),
                    "latency_ms": int((time.time() - started) * 1000),
                    "tool_trace_json": serialize_tool_trace(tool_trace),
                    "answer": answer,
                }
                rows.append(row)
                writer.writerow(row)
                handle.flush()
                if progress_every > 0 and (idx == 1 or idx % progress_every == 0 or idx == total):
                    averages = _averages(rows)
                    print(
                        f"progress {idx}/{total}: "
                        f"recall@{k}={averages['recall_at_k']:.3f} "
                        f"mrr@{k}={averages['mrr_at_k']:.3f} "
                        f"evidence_location_hit@{k}={averages['evidence_location_hit_at_k']:.3f}",
                        flush=True,
                    )

    if summary_out:
        _write_summary(summary_out, rows, k)

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run QASPER through production LLM-routed PageIndex.")
    parser.add_argument("--qasper-json", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--summary-out")
    parser.add_argument("--progress-every", type=int, default=10)
    args = parser.parse_args()

    if not args.openai_key:
        raise SystemExit("--openai-key or OPENAI_API_KEY is required")

    rows = run_agentic_eval(
        Path(args.qasper_json),
        Path(args.out),
        openai_key=args.openai_key,
        model=args.model,
        k=args.k,
        limit=args.limit,
        summary_out=Path(args.summary_out) if args.summary_out else None,
        progress_every=args.progress_every,
    )
    averages = _averages(rows)
    print(
        f"agentic_pageindex: recall@{args.k}={averages['recall_at_k']:.3f} "
        f"mrr@{args.k}={averages['mrr_at_k']:.3f} "
        f"evidence_location_hit@{args.k}={averages['evidence_location_hit_at_k']:.3f}"
    )


if __name__ == "__main__":
    main()
