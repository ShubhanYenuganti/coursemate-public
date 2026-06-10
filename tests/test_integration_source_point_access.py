import api.gdrive as gdrive
import api.notion as notion


class FakeHandler:
    pass


class DenyCourse:
    @staticmethod
    def verify_access(course_id, user_id):
        return False


def _capture_send_json(calls):
    def fake_send_json(_handler, status, payload):
        calls.append((status, payload))

    return fake_send_json


def test_gdrive_add_source_point_rejects_inaccessible_course_before_drive_or_db(monkeypatch):
    calls = []
    monkeypatch.setattr(gdrive, "send_json", _capture_send_json(calls))
    monkeypatch.setattr(gdrive, "Course", DenyCourse, raising=False)
    monkeypatch.setattr(gdrive, "get_valid_token", lambda user_id: "token")

    def fail_drive_api(*_args, **_kwargs):
        raise AssertionError("Drive API should not be called for inaccessible course")

    def fail_get_db(*_args, **_kwargs):
        raise AssertionError("DB should not be opened for inaccessible course")

    monkeypatch.setattr(gdrive, "_drive_api", fail_drive_api)
    monkeypatch.setattr(gdrive, "get_db", fail_get_db)

    gdrive._handle_add_source_point(
        FakeHandler(),
        user_id=7,
        body={"course_id": 42, "external_id": "1AbcdefghijK", "external_title": "Folder"},
    )

    assert calls == [(403, {"error": "Access denied to this course"})]


def test_notion_add_source_point_rejects_inaccessible_course_before_notion_or_db(monkeypatch):
    calls = []
    monkeypatch.setattr(notion, "send_json", _capture_send_json(calls))
    monkeypatch.setattr(notion, "Course", DenyCourse, raising=False)
    monkeypatch.setattr(notion, "_get_notion_token", lambda user_id: "token")

    def fail_resolve(*_args, **_kwargs):
        raise AssertionError("Notion API should not be called for inaccessible course")

    def fail_get_db(*_args, **_kwargs):
        raise AssertionError("DB should not be opened for inaccessible course")

    monkeypatch.setattr(notion, "_resolve_notion_data_source_id", fail_resolve)
    monkeypatch.setattr(notion, "get_db", fail_get_db)

    notion._handle_add_source_point(
        FakeHandler(),
        user_id=7,
        body={"course_id": 42, "external_id": "data-source-id", "external_title": "Database"},
    )

    assert calls == [(403, {"error": "Access denied to this course"})]
