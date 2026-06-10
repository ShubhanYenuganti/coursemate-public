from contextlib import contextmanager
import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lambda" / "integration_poller"))

for module_name in [
    "reportlab",
    "reportlab.lib",
    "reportlab.lib.pagesizes",
    "reportlab.lib.styles",
    "reportlab.lib.units",
    "reportlab.platypus",
]:
    sys.modules.setdefault(module_name, MagicMock())

gdrive_handler = importlib.import_module("lambda.integration_poller.handlers.gdrive")
notion_handler = importlib.import_module("lambda.integration_poller.handlers.notion")


class FakeResult:
    rowcount = 1


class ExistingEmbedJobDb:
    def __init__(self):
        self.status = "skipped"
        self.started_at = "2026-06-01T00:00:00Z"
        self.completed_at = "2026-06-01T00:01:00Z"
        self.error_message = "cancelled"
        self.chunks_created = 3

    def execute(self, sql, params=()):
        assert params == (123,)
        if "ON CONFLICT DO NOTHING" in sql:
            return FakeResult()
        if "ON CONFLICT (material_id) DO UPDATE" in sql:
            self.status = "pending"
            self.started_at = None
            self.completed_at = None
            self.error_message = None
            self.chunks_created = None
            return FakeResult()
        raise AssertionError(f"unexpected SQL: {sql}")


@contextmanager
def db_context(db):
    yield db


@pytest.mark.parametrize("handler", [gdrive_handler, notion_handler])
def test_enqueue_embed_job_resets_existing_terminal_job_to_pending(monkeypatch, handler):
    db = ExistingEmbedJobDb()
    monkeypatch.setattr(handler, "get_db", lambda: db_context(db))

    handler._enqueue_embed_job(123)

    assert db.status == "pending"
    assert db.started_at is None
    assert db.completed_at is None
    assert db.error_message is None
    assert db.chunks_created is None
