#!/usr/bin/env python3
"""
Side-by-side eval: vector RAG vs PageIndex RAG.

Usage:
  python tests/pageindex_eval/eval_runner.py \
    --db-url postgresql://... \
    --openai-key sk-... \
    --course-id 42 \
    --material-ids 1,2,3,4

Outputs results to tests/pageindex_eval/results_YYYY-MM-DD.jsonl
"""
import argparse
import json
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))


def _llm_judge(question: str, answer: str, criteria: str, api_key: str) -> int:
    import requests

    prompt = (
        f"Question: {question}\n\n"
        f"Answer: {answer}\n\n"
        f"Evaluation criteria: {criteria}\n\n"
        "Score the answer 0-3:\n"
        "0 = Does not address the question\n"
        "1 = Partially addresses, missing key criteria\n"
        "2 = Mostly correct, minor gaps\n"
        "3 = Fully correct, meets all criteria\n\n"
        "Respond with only the integer score (0, 1, 2, or 3)."
    )
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 5,
            "temperature": 0,
        },
        timeout=20,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    try:
        return max(0, min(3, int(raw)))
    except ValueError:
        return 0


def _page_hit_rate(expected_pages: list[int], fetched_pages: list[int]) -> float:
    if not expected_pages:
        return 1.0
    hits = sum(1 for page in expected_pages if page in fetched_pages)
    return hits / len(expected_pages)


def run_vector_rag(conn, question: str, course_id: int, material_ids: list[int]) -> dict:
    t0 = time.time()
    try:
        from rag import retrieve_context
        from llm import synthesize

        chunks = retrieve_context(conn, question, material_ids=material_ids)
        answer, _, _, _, _, _, _ = synthesize(
            conn=conn,
            user_id=0,
            ai_provider="openai",
            ai_model="gpt-4o-mini",
            user_message=question,
            chunks=chunks,
            force_context_only=True,
        )
        fetched_pages = list(
            {chunk.get("page_number", 0) for chunk in chunks if chunk.get("page_number")}
        )
    except Exception as exc:
        answer = f"ERROR: {exc}"
        fetched_pages = []
    return {
        "answer": answer,
        "fetched_pages": fetched_pages,
        "latency_ms": int((time.time() - t0) * 1000),
    }


def run_pageindex_rag(
    conn,
    question: str,
    course_id: int,
    material_ids: list[int],
    openai_key: str,
) -> dict:
    from llm import DEFAULT_AGENTIC_MODEL, run_agent_pageindex

    t0 = time.time()
    fetched_pages = []
    try:
        answer, _grounding_refs, tool_trace, _, _, _, _ = run_agent_pageindex(
            conn=conn,
            user_message=question,
            model=DEFAULT_AGENTIC_MODEL,
            api_key=openai_key,
            chat_id=None,
            course_id=course_id,
            context_material_ids=material_ids,
        )
        for trace in tool_trace:
            if trace.get("tool") == "get_page_content":
                from services.query.pageindex_retrieval import _parse_pages

                pages_spec = trace.get("args", {}).get("pages", "")
                fetched_pages.extend(_parse_pages(pages_spec))
    except Exception as exc:
        answer = f"ERROR: {exc}"
    return {
        "answer": answer,
        "fetched_pages": sorted(set(fetched_pages)),
        "latency_ms": int((time.time() - t0) * 1000),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--openai-key", required=True)
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--material-ids", required=True, help="comma-separated")
    args = parser.parse_args()

    import psycopg

    material_ids = [int(x) for x in args.material_ids.split(",")]
    test_cases_path = os.path.join(os.path.dirname(__file__), "test_cases.jsonl")

    with open(test_cases_path) as f:
        test_cases = [json.loads(line) for line in f if line.strip()]

    results = []
    conn = psycopg.connect(args.db_url, row_factory=psycopg.rows.dict_row)

    for tc in test_cases:
        print(f"\nRunning {tc['id']}: {tc['question'][:60]}...")

        vector_result = run_vector_rag(conn, tc["question"], args.course_id, material_ids)
        pageindex_result = run_pageindex_rag(
            conn, tc["question"], args.course_id, material_ids, args.openai_key
        )

        vector_hit = _page_hit_rate(tc["expected_pages"], vector_result["fetched_pages"])
        pageindex_hit = _page_hit_rate(
            tc["expected_pages"], pageindex_result["fetched_pages"]
        )
        vector_score = _llm_judge(
            tc["question"], vector_result["answer"], tc["judge_criteria"], args.openai_key
        )
        pageindex_score = _llm_judge(
            tc["question"],
            pageindex_result["answer"],
            tc["judge_criteria"],
            args.openai_key,
        )

        result = {
            "id": tc["id"],
            "difficulty": tc["difficulty"],
            "vector": {
                "page_hit_rate": vector_hit,
                "answer_score": vector_score,
                "latency_ms": vector_result["latency_ms"],
            },
            "pageindex": {
                "page_hit_rate": pageindex_hit,
                "answer_score": pageindex_score,
                "latency_ms": pageindex_result["latency_ms"],
            },
            "winner": (
                "pageindex"
                if pageindex_score > vector_score
                else ("vector" if vector_score > pageindex_score else "tie")
            ),
        }
        results.append(result)
        print(
            f"  Vector:    hit={vector_hit:.2f} score={vector_score}/3 "
            f"({vector_result['latency_ms']}ms)"
        )
        print(
            f"  PageIndex: hit={pageindex_hit:.2f} score={pageindex_score}/3 "
            f"({pageindex_result['latency_ms']}ms)"
        )

    conn.close()

    out_path = os.path.join(os.path.dirname(__file__), f"results_{date.today()}.jsonl")
    with open(out_path, "w") as f:
        for result in results:
            f.write(json.dumps(result) + "\n")

    print(f"\nResults saved to {out_path}")
    avg_vector_hit = sum(r["vector"]["page_hit_rate"] for r in results) / len(results)
    avg_pageindex_hit = sum(r["pageindex"]["page_hit_rate"] for r in results) / len(results)
    avg_vector_score = sum(r["vector"]["answer_score"] for r in results) / len(results)
    avg_pageindex_score = sum(r["pageindex"]["answer_score"] for r in results) / len(results)
    print("\nSummary:")
    print(f"  Vector    avg hit={avg_vector_hit:.2f}  avg score={avg_vector_score:.2f}")
    print(
        f"  PageIndex avg hit={avg_pageindex_hit:.2f}  "
        f"avg score={avg_pageindex_score:.2f}"
    )
    pageindex_wins = (
        avg_pageindex_hit >= avg_vector_hit and avg_pageindex_score >= avg_vector_score
    )
    print(
        "\n"
        + (
            "PageIndex meets shipping bar"
            if pageindex_wins
            else "PageIndex does not yet meet bar"
        )
    )


if __name__ == "__main__":
    main()
