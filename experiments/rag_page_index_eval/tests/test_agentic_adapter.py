from experiments.rag_page_index_eval.agentic_adapter import (
    QasperPageIndexAdapter,
    QasperSQLitePageIndexAdapter,
    fetched_locations_from_tool_trace,
)
from experiments.rag_page_index_eval.qasper_sqlite_indexer import index_qasper_to_sqlite
from experiments.rag_page_index_eval.types import PageRecord, QueryExample


def _adapter():
    pages = [
        PageRecord("paper-a", 1, "intro text", "Intro", ("Intro",)),
        PageRecord("paper-a", 2, "sparse attention evidence", "Method", ("Method",)),
        PageRecord("paper-b", 1, "rnn evidence", "Background", ("Background",)),
    ]
    queries = [
        QueryExample("q1", "paper-a", "what attention?", {2}, metadata={"title": "Paper A"}),
        QueryExample("q2", "paper-b", "what model?", {1}, metadata={"title": "Paper B"}),
    ]
    return QasperPageIndexAdapter(pages, queries)


def test_adapter_exposes_course_routing_index_in_production_shape():
    adapter = _adapter()

    rows = adapter.get_course_routing_index(conn=None, course_id=1)

    assert rows[0]["material_id"] == 1
    assert rows[0]["title"] == "Paper A"
    assert rows[0]["page_count"] == 2
    assert rows[0]["sections"][0]["start_page"] == 1
    assert rows[0]["sections"][0]["end_page"] == 1
    assert rows[0]["sections"][0]["summary"].startswith("Intro: intro text")
    assert "keywords:" in rows[0]["sections"][0]["summary"]
    assert rows[1]["material_id"] == 2


def test_adapter_fetches_page_content_with_material_and_page_spec():
    adapter = _adapter()

    rows = adapter.get_page_content(conn=None, material_id=1, pages="2-3")

    assert rows == [
        {
            "page_number": 2,
            "text_content": "sparse attention evidence",
            "has_images": False,
        }
    ]


def test_adapter_returns_material_structure_nodes():
    adapter = _adapter()

    structure = adapter.get_material_structure(conn=None, material_id=1)

    assert structure["material_id"] == 1
    assert structure["paper_id"] == "paper-a"
    assert structure["nodes"][0]["title"] == "Intro"
    assert structure["nodes"][0]["source"] in {"regex", "fallback_window"}
    assert structure["nodes"][1]["start_page"] == 2
    assert structure["nodes"][1]["keywords"]


def test_adapter_routing_sections_include_builder_keywords_and_summaries():
    adapter = _adapter()

    rows = adapter.get_course_routing_index(conn=None, course_id=1, material_ids=[1])

    assert rows[0]["sections"][0]["summary"].startswith("Intro:")
    assert "keywords:" in rows[0]["sections"][1]["summary"]
    assert "sparse" in rows[0]["sections"][1]["summary"]


def test_fetched_locations_from_tool_trace_preserves_tool_order_and_uniqueness():
    adapter = _adapter()
    trace = [
        {"tool": "get_material_structure", "args": {"material_id": 1}},
        {"tool": "get_page_content", "args": {"material_id": 1, "pages": "2,1"}},
        {"tool": "get_page_content", "args": {"material_id": 1, "pages": "2"}},
        {"tool": "get_page_content", "args": {"material_id": 2, "pages": "1"}},
    ]

    locations = fetched_locations_from_tool_trace(trace, adapter, limit=5)

    assert locations == [("paper-a", 2), ("paper-a", 1), ("paper-b", 1)]


def test_sqlite_adapter_reads_indexed_qasper_store(tmp_path):
    qasper_json = tmp_path / "mini_qasper.json"
    qasper_json.write_text(
        """
        {
          "paper-a": {
            "title": "Paper A",
            "full_text": [
              {"section_name": "Intro", "paragraphs": ["intro text"]},
              {"section_name": "Method", "paragraphs": ["sparse attention evidence"]}
            ],
            "qas": [
              {
                "question_id": "q1",
                "question": "what attention?",
                "answers": [{"answer": {"free_form_answer": "sparse attention", "evidence": ["sparse attention evidence"]}}]
              }
            ]
          }
        }
        """,
        encoding="utf-8",
    )
    sqlite_db = tmp_path / "qasper.sqlite"

    result = index_qasper_to_sqlite(
        qasper_json=qasper_json,
        sqlite_db=sqlite_db,
        course_id=7,
        index_mode="deterministic",
    )
    adapter = QasperSQLitePageIndexAdapter(sqlite_db, course_id=7)

    assert result["materials_indexed"] == 1
    assert adapter.paper_to_material_id == {"paper-a": 1}
    routing = adapter.get_course_routing_index(conn=None, course_id=7)
    assert routing[0]["title"] == "Paper A"
    assert routing[0]["sections"][1]["summary"].startswith("sparse attention")
    structure = adapter.get_material_structure(conn=None, material_id=1)
    assert structure["title"] == "Paper A"
    pages = adapter.get_page_content(conn=None, material_id=1, pages="2")
    assert pages == [{"page_number": 2, "text_content": "sparse attention evidence", "has_images": False}]


def test_fetched_locations_supports_sqlite_adapter(tmp_path):
    qasper_json = tmp_path / "mini_qasper.json"
    qasper_json.write_text(
        """
        {
          "paper-a": {
            "title": "Paper A",
            "full_text": [{"section_name": "Method", "paragraphs": ["evidence"]}],
            "qas": [{"question_id": "q1", "question": "q?", "answers": []}]
          }
        }
        """,
        encoding="utf-8",
    )
    sqlite_db = tmp_path / "qasper.sqlite"
    index_qasper_to_sqlite(
        qasper_json=qasper_json,
        sqlite_db=sqlite_db,
        course_id=1,
        index_mode="deterministic",
    )
    adapter = QasperSQLitePageIndexAdapter(sqlite_db, course_id=1)

    locations = fetched_locations_from_tool_trace(
        [{"tool": "get_page_content", "args": {"material_id": 1, "pages": "1"}}],
        adapter,
        limit=5,
    )

    assert locations == [("paper-a", 1)]


def test_sqlite_indexer_accepts_huggingface_source(monkeypatch, tmp_path):
    from experiments.rag_page_index_eval import qasper_sqlite_indexer

    def fake_loader(dataset_name, split):
        assert dataset_name == "allenai/qasper"
        assert split == "test"
        return (
            [PageRecord("hf-paper", 1, "hf evidence", "Abstract", ("Abstract",))],
            [QueryExample("hf-q", "hf-paper", "question?", {1}, metadata={"title": "HF Paper"})],
        )

    monkeypatch.setattr(qasper_sqlite_indexer, "load_qasper_huggingface", fake_loader)
    sqlite_db = tmp_path / "qasper.sqlite"

    result = index_qasper_to_sqlite(
        qasper_json=None,
        dataset_source="huggingface",
        hf_dataset="allenai/qasper",
        split="test",
        sqlite_db=sqlite_db,
        course_id=3,
        index_mode="deterministic",
    )
    adapter = QasperSQLitePageIndexAdapter(sqlite_db, course_id=3)

    assert result["materials_indexed"] == 1
    assert adapter.paper_to_material_id == {"hf-paper": 1}


def test_sqlite_indexer_limit_papers_uses_deterministic_paper_id_order(tmp_path):
    qasper_json = tmp_path / "mini_qasper.json"
    qasper_json.write_text(
        """
        {
          "paper-c": {
            "title": "Paper C",
            "full_text": [{"section_name": "C", "paragraphs": ["c"]}],
            "qas": []
          },
          "paper-a": {
            "title": "Paper A",
            "full_text": [{"section_name": "A", "paragraphs": ["a"]}],
            "qas": []
          },
          "paper-b": {
            "title": "Paper B",
            "full_text": [{"section_name": "B", "paragraphs": ["b"]}],
            "qas": []
          }
        }
        """,
        encoding="utf-8",
    )
    sqlite_db = tmp_path / "qasper.sqlite"

    index_qasper_to_sqlite(
        qasper_json=qasper_json,
        sqlite_db=sqlite_db,
        course_id=1,
        limit_papers=2,
        paper_order="paper_id",
        index_mode="deterministic",
    )
    adapter = QasperSQLitePageIndexAdapter(sqlite_db, course_id=1)

    assert adapter.paper_to_material_id == {"paper-a": 1, "paper-b": 2}


def test_sqlite_indexer_llm_enriched_requires_openai_key(tmp_path):
    qasper_json = tmp_path / "mini_qasper.json"
    qasper_json.write_text(
        """
        {
          "paper-a": {
            "title": "Paper A",
            "full_text": [{"section_name": "Method", "paragraphs": ["evidence"]}],
            "qas": []
          }
        }
        """,
        encoding="utf-8",
    )

    try:
        index_qasper_to_sqlite(
            qasper_json=qasper_json,
            sqlite_db=tmp_path / "qasper.sqlite",
            index_mode="llm_enriched",
            openai_key=None,
        )
    except ValueError as exc:
        assert "OPENAI_API_KEY_INDEXER" in str(exc)
    else:
        raise AssertionError("expected llm_enriched indexing to require an OpenAI key")


def test_sqlite_indexer_llm_enriched_writes_llm_fields_and_relations(monkeypatch, tmp_path):
    from experiments.rag_page_index_eval import qasper_sqlite_indexer
    from experiments.rag_page_index_eval.sqlite_store import connect

    qasper_json = tmp_path / "mini_qasper.json"
    qasper_json.write_text(
        """
        {
          "paper-a": {
            "title": "Paper A",
            "full_text": [{"section_name": "Method", "paragraphs": ["attention evidence"]}],
            "qas": []
          },
          "paper-b": {
            "title": "Paper B",
            "full_text": [{"section_name": "Related", "paragraphs": ["attention background"]}],
            "qas": []
          }
        }
        """,
        encoding="utf-8",
    )

    def fake_summarize(prompt, api_key):
        if "Identify relationships" in prompt:
            return '[{"source_id": 1, "target_id": 2, "relation_type": "extends", "shared_tags": ["attention"], "confidence": 0.9}]'
        return "llm summary"

    monkeypatch.setattr(qasper_sqlite_indexer, "summarize", fake_summarize)
    monkeypatch.setattr(qasper_sqlite_indexer, "extract_keywords", lambda prompt, api_key: ["attention", "method"])
    monkeypatch.setattr(qasper_sqlite_indexer, "extract_tags", lambda prompt, api_key: ["attention"])

    sqlite_db = tmp_path / "qasper.sqlite"
    result = index_qasper_to_sqlite(
        qasper_json=qasper_json,
        sqlite_db=sqlite_db,
        index_mode="llm_enriched",
        openai_key="sk-test",
        progress_every=0,
    )

    assert result["relations_stored"] == 2
    assert result["llm_calls"] > 0
    conn = connect(sqlite_db)
    try:
        summary = conn.execute(
            "SELECT material_summary FROM course_material_index WHERE material_id = 1"
        ).fetchone()[0]
        relation_count = conn.execute("SELECT COUNT(*) FROM course_material_relations").fetchone()[0]
    finally:
        conn.close()
    assert summary == "llm summary"
    assert relation_count == 1
