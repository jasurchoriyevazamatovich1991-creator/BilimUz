"""Task 9 — scoring-time guard: an official paper (nonadaptive) SAT practice
table must never score a section whose modules route adaptively, even if the
modules gained a routing_variant after the table was published."""
from fractions import Fraction as F
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.modules.results import official_scoring as osr
from app.modules.results.service import ResultService


def _service(modules):
    module_repo = MagicMock()
    module_repo.list_for_section.return_value = modules
    entries, _ = osr.official_practice_table("sat_practice_test_4", "sat_math")
    table = SimpleNamespace(id="t1", method="range", conversion_type="official_practice_test",
                            test_form="sat_practice_test_4", entries=[{k: str(v) for k, v in e.items()} for e in entries])
    table_repo = MagicMock()
    table_repo.get_current.return_value = table
    svc = ResultService(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
                        conversion_table_repository=table_repo, exam_module_repository=module_repo)
    return svc


SECTION = SimpleNamespace(id="s1", score_component="sat_math")


def test_paper_table_scores_a_non_adaptive_section():
    svc = _service([SimpleNamespace(routing_variant=None)])
    out = svc._scale_section("sat", SECTION, 27.0, False, set(), raw_max=F(54))
    assert (out.lower, out.upper, out.basis) == (F(430), F(460), osr.BASIS_OFFICIAL_PRACTICE_TEST)   # Test 4 Math raw 27


def test_paper_table_refused_when_section_became_adaptive():
    svc = _service([SimpleNamespace(routing_variant=None), SimpleNamespace(routing_variant="hard")])
    out = svc._scale_section("sat", SECTION, 27.0, False, set(), raw_max=F(54))
    assert out.status == osr.STATUS_ADAPTIVE_SECTION
    assert (out.lower, out.upper, out.scaled, out.range) == (None, None, None, None)


def test_scale_mismatch_is_checked_before_adaptivity():
    svc = _service([SimpleNamespace(routing_variant="hard")])
    out = svc._scale_section("sat", SECTION, 10.0, False, set(), raw_max=F(20))
    assert out.status == osr.STATUS_RAW_SCALE_MISMATCH
