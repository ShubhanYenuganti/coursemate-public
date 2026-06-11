from api import sharing


def test_post_non_user_creates_pending(monkeypatch):
    created = {}
    monkeypatch.setattr(sharing.User, "get_by_google_id", staticmethod(lambda g: {"id": 1}))
    monkeypatch.setattr(sharing.User, "get_by_email", staticmethod(lambda e: None))
    monkeypatch.setattr(sharing.Course, "get_by_id", staticmethod(lambda c: {"primary_creator": 1}))
    monkeypatch.setattr(sharing.Course, "get_members", staticmethod(lambda c: []))
    monkeypatch.setattr(
        sharing.PendingInvite,
        "create",
        staticmethod(lambda c, e, i: created.update({"c": c, "e": e}) or True),
    )
    monkeypatch.setattr(
        sharing.PendingInvite,
        "list_for_course",
        staticmethod(lambda c: [{"email": "new@x.com"}]),
    )
    status, payload = sharing.invite_member(google_id="g", course_id=5, email="New@X.com")
    assert status == 200
    assert created == {"c": 5, "e": "new@x.com"}
    assert payload["pending"][0]["email"] == "new@x.com"
