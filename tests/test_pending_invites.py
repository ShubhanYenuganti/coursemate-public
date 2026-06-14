import contextlib

import pytest

from api import models
from api.models import PendingInvite


class FakeCursor:
    def __init__(self, store):
        self.store = store
        self._result = None

    def execute(self, sql, params=None):
        self.store["last"] = (sql, params)
        s = sql.lower()
        if "insert into pending_invites" in s:
            key = (params[0], params[1])
            self.store["rows"][key] = {
                "course_id": params[0],
                "email": params[1],
                "invited_by_id": params[2],
            }
            self._result = {"id": 1}
        elif "select" in s and "pending_invites" in s and "where course_id" in s:
            cid = params[0]
            self._result = [r for k, r in self.store["rows"].items() if k[0] == cid]
        elif "select" in s and "pending_invites" in s and "where email" in s:
            email = params[0]
            self._result = [r for k, r in self.store["rows"].items() if k[1] == email]
        elif "delete from pending_invites" in s:
            for k in list(self.store["rows"]):
                if k[0] == params[0] and k[1] == params[1]:
                    del self.store["rows"][k]

    def fetchone(self):
        return self._result if isinstance(self._result, dict) else None

    def fetchall(self):
        return self._result if isinstance(self._result, list) else []

    def close(self):
        pass


@pytest.fixture
def fake_db(monkeypatch):
    store = {"rows": {}}

    class Conn:
        def cursor(self, *a, **k):
            return FakeCursor(store)

    @contextlib.contextmanager
    def get_db():
        yield Conn()

    monkeypatch.setattr(models, "get_db", get_db)
    return store


def test_create_then_list(fake_db):
    PendingInvite.create(7, "New@X.com".lower(), 3)
    rows = PendingInvite.list_for_course(7)
    assert any(r["email"] == "new@x.com" for r in rows)


def test_claim_attaches_and_is_idempotent(fake_db, monkeypatch):
    calls = []
    monkeypatch.setattr(
        models.Course,
        "add_member",
        staticmethod(lambda c, u, i: calls.append((c, u, i)) or True),
    )
    PendingInvite.create(7, "new@x.com", 3)
    n1 = PendingInvite.claim_for({"id": 99, "email": "new@x.com"})
    n2 = PendingInvite.claim_for({"id": 99, "email": "new@x.com"})
    assert n1 == 1 and n2 == 0
    assert calls == [(7, 99, 3)]
