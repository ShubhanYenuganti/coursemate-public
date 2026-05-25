import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

sys.modules.setdefault(
    "psycopg",
    types.SimpleNamespace(rows=types.SimpleNamespace(dict_row=object)),
)

from db import store_page_texts


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
