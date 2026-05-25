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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local QASPER-style retrieval evals.")
    parser.add_argument("--qasper-json", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    pages, queries = load_qasper_json(Path(args.qasper_json))
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
            hits = retriever.retrieve(query.question, top_k=args.k)
            result = evaluate_hits(query, hits, retriever.variant, args.k)
            rows.append(result.__dict__)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    by_variant = defaultdict(list)
    for row in rows:
        by_variant[row["variant"]].append(row)

    for variant, items in by_variant.items():
        recall = sum(row["recall_at_k"] for row in items) / len(items)
        mrr = sum(row["mrr_at_k"] for row in items) / len(items)
        print(f"{variant}: recall@{args.k}={recall:.3f} mrr@{args.k}={mrr:.3f}")


if __name__ == "__main__":
    main()
