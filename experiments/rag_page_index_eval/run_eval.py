from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from .local_index_adapter import build_index_records
from .metrics import evaluate_hits
from .qasper_loader import load_qasper_json
from .retrievers import (
    HybridRetriever,
    PageBM25Retriever,
    SectionBM25Retriever,
    TwoStageRetriever,
)


def _corpus_stats(pages, queries) -> dict[str, int]:
    evidence_count = sum(len(query.metadata.get("evidence_strings", ())) for query in queries)
    matched_count = sum(len(query.metadata.get("matched_evidence_strings", ())) for query in queries)
    unmatched_count = sum(len(query.metadata.get("unmatched_evidence_strings", ())) for query in queries)
    return {
        "papers": len({page.paper_id for page in pages}),
        "locations": len(pages),
        "queries": len(queries),
        "answerable_queries": sum(1 for query in queries if query.gold_pages),
        "evidence_strings": evidence_count,
        "matched_evidence_strings": matched_count,
        "unmatched_evidence_strings": unmatched_count,
    }


def _averages(rows: list[dict]) -> dict[str, dict[str, float]]:
    by_variant = defaultdict(list)
    for row in rows:
        by_variant[row["variant"]].append(row)

    metrics = [
        "recall_at_k",
        "mrr_at_k",
        "ndcg_at_k",
        "evidence_location_hit_at_k",
        "answerability_coverage",
    ]
    return {
        variant: {
            metric: sum(row[metric] for row in items) / len(items)
            for metric in metrics
        }
        for variant, items in by_variant.items()
    }


def _write_summary(path: Path, stats: dict[str, int], averages: dict[str, dict[str, float]], k: int) -> None:
    lines = [
        "# Real QASPER Evidence-Location Eval",
        "",
        "## Corpus",
        "",
        f"- papers: {stats['papers']}",
        f"- evidence locations: {stats['locations']}",
        f"- queries: {stats['queries']}",
        f"- answerable queries: {stats['answerable_queries']}",
        f"- evidence strings: {stats['evidence_strings']}",
        f"- matched evidence strings: {stats['matched_evidence_strings']}",
        f"- unmatched evidence strings: {stats['unmatched_evidence_strings']}",
        "",
        "## Metrics",
        "",
        f"| Variant | Recall@{k} | MRR@{k} | NDCG@{k} | Evidence Location Hit@{k} | Answerability Coverage |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant, metrics in averages.items():
        lines.append(
            "| {variant} | {recall:.3f} | {mrr:.3f} | {ndcg:.3f} | {hit:.3f} | {coverage:.3f} |".format(
                variant=variant,
                recall=metrics["recall_at_k"],
                mrr=metrics["mrr_at_k"],
                ndcg=metrics["ndcg_at_k"],
                hit=metrics["evidence_location_hit_at_k"],
                coverage=metrics["answerability_coverage"],
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_eval(qasper_json: Path, out: Path, k: int = 5, summary_out: Path | None = None) -> list[dict]:
    pages, queries = load_qasper_json(qasper_json)
    if not queries:
        raise SystemExit("no query examples found")

    paper_ids = sorted({page.paper_id for page in pages})
    nodes = []
    for paper_id in paper_ids:
        nodes.extend(build_index_records(paper_id, pages))

    retrievers = [
        PageBM25Retriever(pages),
        SectionBM25Retriever(nodes),
        TwoStageRetriever(pages, nodes),
        HybridRetriever(pages, nodes),
    ]

    rows = []
    for retriever in retrievers:
        for query in queries:
            hits = retriever.retrieve(query.question, top_k=k)
            result = evaluate_hits(query, hits, retriever.variant, k)
            rows.append(result.__dict__)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    averages = _averages(rows)
    if summary_out is not None:
        _write_summary(summary_out, _corpus_stats(pages, queries), averages, k)

    for variant, metrics in averages.items():
        print(
            f"{variant}: recall@{k}={metrics['recall_at_k']:.3f} "
            f"mrr@{k}={metrics['mrr_at_k']:.3f} "
            f"evidence_location_hit@{k}={metrics['evidence_location_hit_at_k']:.3f}"
        )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local QASPER evidence-location retrieval evals.")
    parser.add_argument("--qasper-json", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--summary-out")
    args = parser.parse_args()

    run_eval(
        Path(args.qasper_json),
        Path(args.out),
        k=args.k,
        summary_out=Path(args.summary_out) if args.summary_out else None,
    )


if __name__ == "__main__":
    main()
