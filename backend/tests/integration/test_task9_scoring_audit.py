"""
Task 9 — regression tests for defects found in the final scoring audit, plus
cross-cutting checks (permissions, ownership) against real PostgreSQL.
"""
from tests.integration.test_task4_scaled_scoring import API, Ctx, _headers, _section, _set_profile, _take, _test, _user
from tests.integration.test_task7_official_conversion import _correct, _table
from tests.integration.test_task8_sat_practice_tables import _official, _sat


# The scoring-time adaptive guard (defect M-2) is unit-tested in
# app/modules/results/tests/test_task9_scoring_audit.py.


def test_scoring_tables_are_admin_only(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx, 3, 3)
    teacher = _user(pg_session, "Teacher")
    pg_session.commit()
    th = _headers(client, teacher)
    url = f"{API}/tests/exam-sections/{rw['id']}/conversion-tables"
    for h in (th, ctx.sh):
        assert client.get(url, headers=h).status_code == 403
        assert client.post(url, json=_official(), headers=h).status_code == 403
        assert client.put(f"{API}/tests/{test.id}/scoring-profile", json={"scoring_profile": "gre"}, headers=h).status_code == 403
    assert client.get(url).status_code == 401


def test_students_see_only_their_own_scaled_results(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, rw, math, qs = _sat(ctx, 3, 3)
    mine = _take(ctx, test, _correct(qs["rw"], 1))
    other = _user(pg_session)
    pg_session.commit()
    assert client.get(f"{API}/results/{mine['id']}", headers=_headers(client, other)).status_code == 404
    assert client.get(f"{API}/results/{mine['id']}").status_code == 401


def test_gre_scales_and_no_universal_table(client, pg_session):
    ctx = Ctx(client, pg_session)
    test = _test(pg_session, status="published")
    pg_session.commit()
    assert _set_profile(ctx, test, "gre").status_code == 200
    v = _section(ctx, test, "Verbal", 0, "gre_verbal")
    awa = _section(ctx, test, "AWA", 1, "gre_analytical_writing")
    # Verbal/Quant: 130–170 by 1 — values outside are refused even for estimates.
    for bad in ([{"raw": 0, "scaled": 129}], [{"raw": 0, "scaled": 171}], [{"raw": 0, "scaled": 150.5}]):
        assert _table(ctx, v["id"], {"method": "exact", "conversion_type": "estimate", "entries": bad}).status_code == 422
    # No official GRE table exists; AWA is never table-converted.
    assert _table(ctx, v["id"], _official()).status_code == 422
    assert _table(ctx, awa["id"], {"method": "exact", "entries": [{"raw": 0, "scaled": 3}]}).status_code == 422
