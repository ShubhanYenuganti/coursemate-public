from contextlib import contextmanager
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lambda" / "integration_poller"))
gdrive_handler = importlib.import_module("lambda.integration_poller.handlers.gdrive")


class FakeDb:
    def __init__(self):
        self.registered = []
        self.updated_source_points = []

    def execute(self, sql, params=()):
        if "SELECT external_id FROM materials" in sql:
            return FakeResult([])
        if "INSERT INTO materials" in sql:
            self.registered.append(params)
            return FakeResult([{"id": len(self.registered)}])
        if "UPDATE integration_source_points" in sql:
            self.updated_source_points.append(params[0])
            return FakeResult([])
        return FakeResult([])


class FakeResult:
    def __init__(self, rows):
        self._rows = rows
        self.rowcount = len(rows)

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


@contextmanager
def fake_db_context(db):
    yield db


def test_gdrive_discovery_ignores_unsupported_file_types(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(gdrive_handler, "get_db", lambda: fake_db_context(db))
    monkeypatch.setattr(
        gdrive_handler,
        "_list_all_folder_files",
        lambda folder_id, token: [
            {
                "id": "doc-1",
                "name": "Lecture Notes",
                "mimeType": gdrive_handler.GOOGLE_DOC_MIME,
                "modifiedTime": "2026-06-01T00:00:00Z",
            },
            {
                "id": "docx-1",
                "name": "Raw Word File",
                "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "modifiedTime": "2026-06-01T00:00:00Z",
            },
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
    monkeypatch.setattr(gdrive_handler, "_get_drive_file_as_pdf", lambda *_args: b"%PDF")
    monkeypatch.setattr(gdrive_handler, "_upload_pdf_to_s3", lambda file_id, _bytes: f"gdrive/{file_id}.pdf")
    monkeypatch.setattr(gdrive_handler, "_update_material_after_upload", lambda *_args: None)
    monkeypatch.setattr(gdrive_handler, "_enqueue_embed_job", lambda *_args: None)
    monkeypatch.setattr(gdrive_handler, "_trigger_index", lambda *_args: None)

    gdrive_handler.sync_source_point(
        {
            "id": 11,
            "user_id": 7,
            "course_id": 42,
            "external_id": "folder-1",
        },
        token="token",
    )

    registered_external_ids = [params[4] for params in db.registered]
    assert registered_external_ids == ["doc-1"]
