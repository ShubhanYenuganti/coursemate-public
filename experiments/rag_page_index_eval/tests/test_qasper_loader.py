from pathlib import Path

from experiments.rag_page_index_eval.qasper_loader import load_qasper_json


def test_load_qasper_json_creates_pages_and_queries():
    fixture = Path("experiments/rag_page_index_eval/fixtures/mini_qasper.json")

    pages, queries = load_qasper_json(fixture)

    assert len(pages) == 30
    assert len(queries) == 18
    assert queries[0].gold_pages


def test_load_qasper_json_reads_real_answer_evidence(tmp_path):
    fixture = tmp_path / "real_qasper.json"
    fixture.write_text(
        """
        {
          "paper-1": {
            "title": "Real Paper",
            "full_text": [
              {
                "section_name": "Introduction",
                "paragraphs": ["The paper motivates retrieval evaluation."]
              },
              {
                "section_name": "Method",
                "paragraphs": ["The model uses sparse attention for long documents."]
              }
            ],
            "qas": [
              {
                "question_id": "q1",
                "question": "What attention method is used?",
                "answers": [
                  {
                    "answer": {
                      "free_form_answer": "Sparse attention.",
                      "evidence": ["sparse attention for long documents"]
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

    pages, queries = load_qasper_json(fixture)

    assert [page.section_name for page in pages] == ["Introduction", "Method"]
    assert queries[0].paper_id == "paper-1"
    assert queries[0].gold_pages == {2}
    assert queries[0].answer_texts == ("Sparse attention.",)
    assert queries[0].metadata["evidence_strings"] == ("sparse attention for long documents",)
    assert queries[0].metadata["matched_evidence_strings"] == ("sparse attention for long documents",)
    assert queries[0].metadata["unmatched_evidence_strings"] == ()


def test_load_qasper_json_reports_unmatched_real_evidence(tmp_path):
    fixture = tmp_path / "real_qasper_unmatched.json"
    fixture.write_text(
        """
        [
          {
            "paper_id": "paper-2",
            "title": "Another Real Paper",
            "full_text": [
              {"section_name": "Results", "paragraphs": ["Accuracy improved on the test set."]}
            ],
            "qas": [
              {
                "question_id": "q2",
                "question": "What improved?",
                "answers": [
                  {
                    "answer": {
                      "free_form_answer": "Accuracy.",
                      "evidence": ["This evidence string is absent."]
                    }
                  }
                ]
              }
            ]
          }
        ]
        """,
        encoding="utf-8",
    )

    _, queries = load_qasper_json(fixture)

    assert queries[0].gold_pages == set()
    assert queries[0].metadata["evidence_strings"] == ("This evidence string is absent.",)
    assert queries[0].metadata["matched_evidence_strings"] == ()
    assert queries[0].metadata["unmatched_evidence_strings"] == ("This evidence string is absent.",)
