import json
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

sys.modules.setdefault(
    "psycopg",
    types.SimpleNamespace(rows=types.SimpleNamespace(dict_row=object)),
)

from db import store_page_texts, store_page_visuals


class FakeConn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))


def test_store_page_texts_accepts_section_path():
    conn = FakeConn()
    rows = [
        {
            "page_number": 1,
            "text_content": "Intro",
            "has_images": False,
            "section_name": "Introduction",
            "section_path": ["Paper", "Introduction"],
        }
    ]

    store_page_texts(conn, material_id=42, page_rows=rows)

    sql, params = conn.calls[0]
    assert "section_path" in sql
    assert params[-1] == '["Paper", "Introduction"]'


def test_store_page_visuals_upserts_correct_columns():
    conn = FakeConn()
    visuals = {
        "visual_summary": "A slide with a neural network diagram",
        "detected_figures": [{"label": "Figure 1", "description": "3-layer network"}],
        "detected_tables": [],
    }
    store_page_visuals(conn, material_id=7, page_number=3, visuals=visuals)

    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert "material_page_visuals" in sql
    assert "ON CONFLICT" in sql
    assert "%s::jsonb" in sql
    assert params[0] == 7        # material_id
    assert params[1] == 3        # page_number
    assert "neural network" in params[2]   # visual_summary
    assert json.loads(params[3]) == [
        {"label": "Figure 1", "description": "3-layer network"}
    ]
    assert json.loads(params[4]) == []


def test_store_page_visuals_handles_empty_visuals():
    conn = FakeConn()
    store_page_visuals(conn, material_id=1, page_number=1, visuals={
        "visual_summary": "",
        "detected_figures": [],
        "detected_tables": [],
    })
    sql, params = conn.calls[0]
    assert params[2] == ""
    assert json.loads(params[3]) == []
    assert json.loads(params[4]) == []


def test_store_page_visuals_defaults_missing_keys():
    conn = FakeConn()
    store_page_visuals(conn, material_id=1, page_number=1, visuals={})
    sql, params = conn.calls[0]
    assert "%s::jsonb" in sql
    assert params[2] == ""
    assert json.loads(params[3]) == []
    assert json.loads(params[4]) == []
