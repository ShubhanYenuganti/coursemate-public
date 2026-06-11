from api.models import PendingInvite


def test_claim_for_calls_add_member(monkeypatch):
    added = []
    import api.models as m

    monkeypatch.setattr(
        m.Course,
        "add_member",
        staticmethod(lambda c, u, i: added.append((c, u, i)) or True),
    )
    monkeypatch.setattr(PendingInvite, "claim_for", PendingInvite.claim_for)

    import api.auth as auth

    calls = {"n": 0}
    monkeypatch.setattr(
        auth,
        "PendingInvite",
        type("P", (), {"claim_for": staticmethod(lambda u: calls.__setitem__("n", calls["n"] + 1))}),
    )
    auth.claim_pending_invites({"id": 1, "email": "a@b.com"})
    assert calls["n"] == 1
