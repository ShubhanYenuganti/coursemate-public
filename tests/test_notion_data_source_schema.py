import api.notion as notion


class FakeHandler:
    pass


def test_search_preserves_data_source_id_when_url_contains_database_id():
    item = {
        "object": "data_source",
        "id": "11111111-1111-1111-1111-111111111111",
        "url": "https://www.notion.so/22222222222222222222222222222222",
    }

    assert notion._canonical_notion_id(item) == "11111111-1111-1111-1111-111111111111"


def test_create_page_target_accepts_data_source_id_without_database_lookup(monkeypatch):
    calls = []

    def fake_notion_api(method, path, token, body=None, user_id=None):
        calls.append((method, path, body))
        if path == "/data_sources/ds-1":
            return {
                "object": "data_source",
                "id": "ds-1",
                "properties": {
                    "Name": {"type": "title"},
                    "Notes": {"type": "rich_text"},
                },
            }, None, None
        if path == "/databases/ds-1":
            raise AssertionError("data_source_id should not be fetched as a database")
        if path == "/pages":
            return {"id": "page-1", "url": "https://notion.so/page-1"}, None, None
        raise AssertionError(f"unexpected Notion call: {method} {path}")

    monkeypatch.setattr(notion, "_notion_api", fake_notion_api)

    page_id, page_url, err = notion._create_page_in_database(
        "ds-1", "Exported Quiz", "token", user_id=9
    )

    assert err is None
    assert page_id == "page-1"
    assert page_url == "https://notion.so/page-1"
    assert calls[-1] == (
        "POST",
        "/pages",
        {
            "parent": {"type": "data_source_id", "data_source_id": "ds-1"},
            "properties": {
                "Name": {
                    "title": [{"type": "text", "text": {"content": "Exported Quiz"}}]
                }
            },
        },
    )


def test_create_database_target_uses_initial_data_source_schema(monkeypatch):
    sent = []
    calls = []

    monkeypatch.setattr(notion, "_get_notion_token", lambda user_id: "token")
    monkeypatch.setattr(
        notion,
        "send_json",
        lambda _handler, status, payload: sent.append((status, payload)),
    )

    def fake_notion_api(method, path, token, body=None, user_id=None):
        calls.append((method, path, body))
        if method == "POST" and path == "/databases":
            return {
                "id": "database-1",
                "url": "https://notion.so/database-1",
                "title": [{"plain_text": "Course Exports"}],
            }, None, None
        raise AssertionError(f"unexpected Notion call: {method} {path}")

    monkeypatch.setattr(notion, "_notion_api", fake_notion_api)

    notion._handle_create_target(
        FakeHandler(),
        user_id=9,
        body={
            "type": "database",
            "title": "Course Exports",
            "parent_id": "parent-page",
        },
    )

    assert sent == [
        (
            200,
            {
                "id": "database-1",
                "title": "Course Exports",
                "type": "database",
                "notion_url": "https://notion.so/database-1",
            },
        )
    ]
    create_body = calls[0][2]
    assert "properties" not in create_body
    assert create_body["initial_data_source"]["properties"] == {
        "Front": {"title": {}},
        "Back": {"rich_text": {}},
        "Hint": {"rich_text": {}},
    }
