"""Unit tests for pure timer/randomization functions — no DB, no mocks."""
import uuid
from datetime import datetime, timedelta, timezone

from app.modules.attempts.validators import build_question_order, compute_expiry, is_expired


def test_compute_expiry_adds_duration_minutes():
    start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert compute_expiry(start, 60) == datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)


def test_is_expired_false_before_deadline():
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert is_expired(future) is False


def test_is_expired_true_after_deadline():
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert is_expired(past) is True


def test_is_expired_false_when_none():
    assert is_expired(None) is False


def test_build_question_order_preserves_all_ids():
    ids = [uuid.uuid4() for _ in range(10)]
    ordered = build_question_order(ids, shuffle=True)
    assert set(ordered) == set(ids)
    assert len(ordered) == len(ids)


def test_build_question_order_no_shuffle_preserves_input_order():
    ids = [uuid.uuid4() for _ in range(5)]
    assert build_question_order(ids, shuffle=False) == ids


# --- Sprint 78 — group-aware shuffle (QuestionGroup contiguity) --------


def _find_blocks(ordered: list[uuid.UUID], id_to_group: dict[uuid.UUID, uuid.UUID | None]) -> list[list[uuid.UUID]]:
    """Collapses `ordered` into runs of consecutive same-group ids
    (None never collapses with another None — each ungrouped question
    is its own block), for asserting contiguity regardless of which
    block order the shuffle picked."""
    blocks: list[list[uuid.UUID]] = []
    for qid in ordered:
        gid = id_to_group[qid]
        if gid is not None and blocks and id_to_group[blocks[-1][-1]] == gid:
            blocks[-1].append(qid)
        else:
            blocks.append([qid])
    return blocks


def test_build_question_order_shuffle_false_ignores_group_ids_byte_identical():
    """Invariant 9 — shuffle=False behavior is completely untouched by
    this sprint, group_ids or not."""
    ids = [uuid.uuid4() for _ in range(5)]
    group = uuid.uuid4()
    group_ids = [group, group, None, None, None]
    assert build_question_order(ids, shuffle=False, group_ids=group_ids) == ids


def test_build_question_order_shuffle_true_without_group_ids_is_plain_shuffle():
    """Backward compatibility — omitting group_ids (every pre-Sprint-78
    caller) is byte-identical to the old plain-shuffle behavior; this
    is also exactly what ModuleExecutionService's shuffle=False call
    continues to get even if it were ever passed group_ids."""
    ids = [uuid.uuid4() for _ in range(20)]
    ordered = build_question_order(ids, shuffle=True)
    assert set(ordered) == set(ids)
    assert len(ordered) == len(ids)


def test_build_question_order_grouped_shuffle_keeps_every_group_contiguous():
    """Invariants 1-5: every id exactly once, no dup/missing, grouped
    questions never split — across many trials, since random.shuffle's
    block order itself is non-deterministic by design."""
    group_a, group_b = uuid.uuid4(), uuid.uuid4()
    a1, a2, a3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    b1, b2 = uuid.uuid4(), uuid.uuid4()
    u1, u2 = uuid.uuid4(), uuid.uuid4()
    ids = [a1, a2, a3, b1, b2, u1, u2]
    group_ids = [group_a, group_a, group_a, group_b, group_b, None, None]
    id_to_group = dict(zip(ids, group_ids))

    for _ in range(50):
        ordered = build_question_order(ids, shuffle=True, group_ids=group_ids)
        assert set(ordered) == set(ids)
        assert len(ordered) == len(ids)
        blocks = _find_blocks(ordered, id_to_group)
        a_block = next(b for b in blocks if a1 in b)
        b_block = next(b for b in blocks if b1 in b)
        assert a_block == [a1, a2, a3]  # internal order preserved exactly
        assert b_block == [b1, b2]
        assert sorted(len(b) for b in blocks) == [1, 1, 2, 3]  # u1, u2 each their own block


def test_build_question_order_grouped_shuffle_randomizes_block_sequence():
    """The block SEQUENCE itself is actually randomized, not just
    internally stable — guards against an implementation that
    accidentally always returns the same block order."""
    group_a, group_b = uuid.uuid4(), uuid.uuid4()
    ids = [uuid.uuid4() for _ in range(2)] + [uuid.uuid4() for _ in range(2)]
    a1, a2, b1, b2 = ids
    group_ids = [group_a, group_a, group_b, group_b]

    seen_first_block_is_a = set()
    for _ in range(50):
        ordered = build_question_order(ids, shuffle=True, group_ids=group_ids)
        seen_first_block_is_a.add(ordered[0] in (a1, a2))
    assert seen_first_block_is_a == {True, False}  # both block orders observed


def test_build_question_order_single_question_group_is_a_valid_block():
    group = uuid.uuid4()
    solo = uuid.uuid4()
    other = uuid.uuid4()
    ids = [solo, other]
    group_ids = [group, None]
    ordered = build_question_order(ids, shuffle=True, group_ids=group_ids)
    assert set(ordered) == {solo, other}


def test_build_question_order_all_ungrouped_behaves_like_plain_shuffle():
    ids = [uuid.uuid4() for _ in range(10)]
    group_ids = [None] * 10
    ordered = build_question_order(ids, shuffle=True, group_ids=group_ids)
    assert set(ordered) == set(ids)
    assert len(ordered) == len(ids)


def test_build_question_order_mismatched_group_ids_length_falls_back_to_plain_shuffle():
    """Defensive — a caller bug (lists out of sync) must never crash or
    silently corrupt the question set; it degrades to the safe old
    behavior instead."""
    ids = [uuid.uuid4() for _ in range(5)]
    ordered = build_question_order(ids, shuffle=True, group_ids=[uuid.uuid4()])
    assert set(ordered) == set(ids)
    assert len(ordered) == len(ids)
