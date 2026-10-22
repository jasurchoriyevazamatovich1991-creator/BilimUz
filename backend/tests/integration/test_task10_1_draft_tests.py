"""Task 10.1 — draft test metadata is visible only to content staff."""
import uuid

import pytest

from app.modules.subjects.models import Subject
from app.modules.tests.models import Test
from tests.integration.test_task10_1_registration_and_accounts import _token, _user

API = "/api/v1"


def _tests(db):
    s = Subject(name=f"Draft S-{uuid.uuid4()}")
    db.add(s)
    db.flush()
    marker = f"vis-{uuid.uuid4().hex[:8]}"
    made = {}
    for status in ("draft", "published", "archived"):
        t = Test(subject_id=s.id, title=f"{marker} {status}", duration=30, question_count=0, status=status,
                 shuffle_questions=False, shuffle_answers=False)
        db.add(t)
        db.flush()
        made[status] = t
    db.commit()
    return marker, made


def _headers(client, db, who):
    return {} if who == "anonymous" else _token(client, _user(db, who))


def _titles(client, marker, headers, status=None):
    params = {"search": marker, "per_page": 100, **({"status": status} if status else {})}
    r = client.get(f"{API}/tests", params=params, headers=headers)
    assert r.status_code == 200, r.json()
    return sorted(i["title"].split()[-1] for i in r.json()["data"]["items"])


@pytest.mark.parametrize("who", ["anonymous", "Student"])
def test_non_staff_see_only_published(client, pg_session, who):
    marker, made = _tests(pg_session)
    h = _headers(client, pg_session, who)
    assert _titles(client, marker, h) == ["published"]
    for status in ("draft", "archived", "published"):
        assert _titles(client, marker, h, status) == ["published"]          # ?status= cannot widen it
    assert client.get(f"{API}/tests/{made['draft'].id}", headers=h).status_code == 404
    assert client.get(f"{API}/tests/{made['published'].id}", headers=h).status_code == 200
    assert client.get(f"{API}/tests/{made['archived'].id}", headers=h).status_code == 200   # past results link here


@pytest.mark.parametrize("who", ["Teacher", "Admin", "Super Admin"])
def test_staff_see_every_status(client, pg_session, who):
    marker, made = _tests(pg_session)
    h = _headers(client, pg_session, who)
    assert _titles(client, marker, h) == ["archived", "draft", "published"]
    assert _titles(client, marker, h, "draft") == ["draft"]
    for t in made.values():
        assert client.get(f"{API}/tests/{t.id}", headers=h).status_code == 200


def test_invalid_token_is_rejected_not_downgraded(client, pg_session):
    marker, made = _tests(pg_session)
    r = client.get(f"{API}/tests", params={"search": marker}, headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
