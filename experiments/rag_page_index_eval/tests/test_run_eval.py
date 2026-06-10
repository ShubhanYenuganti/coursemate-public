import csv
from pathlib import Path

from experiments.rag_page_index_eval.run_eval import run_eval


def test_run_eval_writes_evidence_location_metrics_and_summary(tmp_path):
    fixture = tmp_path / "real_qasper.json"
    out = tmp_path / "results.csv"
    summary = tmp_path / "summary.md"
    fixture.write_text(
        """
        {
          "paper-1": {
            "title": "Real Paper",
            "full_text": [
              {"section_name": "Intro", "paragraphs": ["Retrieval finds grounding evidence."]},
              {"section_name": "Method", "paragraphs": ["Sparse attention handles long documents."]}
            ],
            "qas": [
              {
                "question_id": "q1",
                "question": "What handles long documents?",
                "answers": [
                  {
                    "answer": {
                      "free_form_answer": "Sparse attention.",
                      "evidence": ["Sparse attention handles long documents."]
                    }
                  }
                ]
              }
            ]
          }
        }
        """,
        encoding="utf-8",
    )

    run_eval(fixture, out, k=5, summary_out=summary)

    rows = list(csv.DictReader(out.open()))
    assert rows
    assert "evidence_location_hit_at_k" in rows[0]
    assert "page_range_hit_at_k" not in rows[0]

    text = summary.read_text(encoding="utf-8")
    assert "Evidence Location Hit@5" in text
    assert "Answerability Coverage" in text
    assert "papers: 1" in text
