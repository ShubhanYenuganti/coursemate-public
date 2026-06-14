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


def test_get_collaborator_receives_empty_pending(monkeypatch):
    sent = {}
    pending_invites = [{"email": "secret@x.com"}]

    monkeypatch.setattr(sharing, "authenticate_request", lambda h: ("collab-google", None))
    monkeypatch.setattr(
        sharing,
        "send_json",
        lambda h, status, payload: sent.update({"status": status, "payload": payload}),
    )
    monkeypatch.setattr(
        sharing.User,
        "get_by_google_id",
        staticmethod(lambda g: {"id": 2, "email": "collab@x.com"}),
    )
    monkeypatch.setattr(sharing.Course, "verify_access", staticmethod(lambda c, u: True))
    monkeypatch.setattr(
        sharing.Course,
        "get_by_id",
        staticmethod(lambda c: {"id": c, "primary_creator": 1}),
    )
    monkeypatch.setattr(
        sharing.Course,
        "get_members",
        staticmethod(
            lambda c: [
                {
                    "id": 2,
                    "name": "Collaborator",
                    "email": "collab@x.com",
                    "picture": None,
                    "role": "viewer",
                    "joined_at": None,
                    "invited_by_name": "Owner",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        sharing.PendingInvite,
        "list_for_course",
        staticmethod(lambda c: pending_invites),
    )

    handler = object.__new__(sharing.handler)
    handler.path = "/api/sharing?course_id=5"
    handler.do_GET()

    assert sent["status"] == 200
    assert sent["payload"]["members"][0]["email"] == "collab@x.com"
    assert sent["payload"]["pending"] == []
    assert sent["payload"]["pending"] != pending_invites
