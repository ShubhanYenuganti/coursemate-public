from contextlib import contextmanager

import api.material as material_api


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.rows = [{"external_id": "file-1"}, {"external_id": "file-2"}]
        self.rowcount = 2

    def execute(self, sql, params=()):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


@contextmanager
def fake_db(cursor):
    yield FakeConn(cursor)


class FakeUser:
    @staticmethod
    def get_by_google_id(google_id):
        return {"id": 7}


class AllowCourse:
    @staticmethod
    def verify_access(course_id, user_id):
        return course_id == 42 and user_id == 7


class FakeHandler:
    pass


def test_cancel_sync_jobs_marks_matching_embed_jobs_skipped(monkeypatch):
    sent = []
    cursor = FakeCursor()
    handler = material_api.handler.__new__(material_api.handler)

    monkeypatch.setattr(material_api, "User", FakeUser)
    monkeypatch.setattr(material_api, "Course", AllowCourse)
    monkeypatch.setattr(material_api, "get_db", lambda: fake_db(cursor))
    monkeypatch.setattr(
        material_api,
        "send_json",
        lambda _handler, status, payload: sent.append((status, payload)),
    )

    handler._cancel_sync_jobs(
        "google-1",
        {
            "course_id": 42,
            "source_type": "gdrive",
            "external_ids": ["file-1", "file-2"],
        },
    )

    assert sent == [
        (
            200,
            {"cancelled": 2, "external_ids": ["file-1", "file-2"]},
        )
    ]
    sql, params = cursor.executed[0]
    assert "SET status = 'skipped'" in sql
    assert "j.status NOT IN ('done', 'failed', 'skipped', 'up_to_date')" in sql
    assert params == (42, "gdrive", ["file-1", "file-2"])
