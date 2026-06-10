from contextlib import contextmanager
import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

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
    def __init__(self, rows=None, rowcount=0):
        self._rows = rows or []
        self.rowcount = rowcount

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class ReconcileDb:
    def __init__(self, known_ids):
        self.known_ids = list(known_ids)
        self.unsynced_ids = []

    def execute(self, sql, params=()):
        if "SELECT external_id FROM materials" in sql and "sync = TRUE" not in sql:
            return FakeResult([{"external_id": external_id} for external_id in self.known_ids])
        if "UPDATE materials" in sql and "sync = FALSE" in sql:
            missing_ids = list(params[1])
            self.unsynced_ids.extend(missing_ids)
            return FakeResult(rowcount=len(missing_ids))
        if "SELECT external_id FROM materials" in sql and "sync = TRUE" in sql:
            rows = [
                {"external_id": external_id}
                for external_id in self.known_ids
                if external_id not in set(self.unsynced_ids)
            ]
            return FakeResult(rows)
        return FakeResult([])


@contextmanager
def db_context(db):
    yield db


def test_gdrive_background_sweep_marks_missing_remote_files_unsynced(monkeypatch):
    db = ReconcileDb(["present-file", "deleted-file"])
    monkeypatch.setattr(gdrive_handler, "get_db", lambda: db_context(db))
    monkeypatch.setattr(
        gdrive_handler,
        "_list_all_folder_files",
        lambda folder_id, token: [
            {
                "id": "present-file",
                "name": "Present",
                "mimeType": gdrive_handler.GOOGLE_DOC_MIME,
                "modifiedTime": "2026-06-01T00:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(
        gdrive_handler,
        "_fetch_file_metadata",
        lambda file_id, token: {
            "id": file_id,
            "name": file_id,
            "mimeType": gdrive_handler.GOOGLE_DOC_MIME,
            "modifiedTime": "2026-06-01T00:00:00Z",
        },
    )
    monkeypatch.setattr(gdrive_handler, "_upsert_material", lambda *_args: (1, False))
    monkeypatch.setattr(gdrive_handler, "_doc_type_changed", lambda *_args: False)

    gdrive_handler.sync_source_point(
        {"id": 11, "user_id": 7, "course_id": 42, "external_id": "folder-1"},
        token="token",
    )

    assert db.unsynced_ids == ["deleted-file"]


def test_notion_background_sweep_marks_missing_remote_pages_unsynced(monkeypatch):
    db = ReconcileDb(["present-page", "deleted-page"])
    monkeypatch.setattr(notion_handler, "get_db", lambda: db_context(db))
    monkeypatch.setattr(
        notion_handler,
        "_list_all_database_pages",
        lambda database_id, token: [
            {
                "id": "present-page",
                "last_edited_time": "2026-06-01T00:00:00Z",
                "properties": {"Name": {"type": "title", "title": [{"plain_text": "Present"}]}},
                "url": "https://notion.so/present",
            }
        ],
    )
    monkeypatch.setattr(
        notion_handler,
        "_notion_get",
        lambda path, token, params=None: {
            "id": "present-page",
            "last_edited_time": "2026-06-01T00:00:00Z",
            "properties": {"Name": {"type": "title", "title": [{"plain_text": "Present"}]}},
            "url": "https://notion.so/present",
        },
    )
    monkeypatch.setattr(notion_handler, "_upsert_material", lambda *_args, **_kwargs: (1, False))
    monkeypatch.setattr(notion_handler, "_doc_type_changed", lambda *_args: False)

    notion_handler.sync_source_point(
        {"id": 12, "user_id": 7, "course_id": 42, "external_id": "data-source-1"},
        token="token",
    )

    assert db.unsynced_ids == ["deleted-page"]
