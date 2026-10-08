"""Pure functions — no I/O, no DB, reusable from the service layer.
Timer arithmetic and randomization live here specifically so they're
unit-testable without a database (see tests/test_attempt_validators.py)."""
import random
import uuid
from datetime import datetime, timedelta, timezone


def compute_expiry(start_time: datetime, duration_minutes: int) -> datetime:
    return start_time + timedelta(minutes=duration_minutes)


def is_expired(expires_at: datetime | None, now: datetime | None = None) -> bool:
    if expires_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now > expires_at


def build_question_order(
    question_ids: list[uuid.UUID], shuffle: bool, group_ids: list[uuid.UUID | None] | None = None,
) -> list[uuid.UUID]:
    """Called exactly once, at attempt/module start. The result is
    persisted (test_attempts.question_order /
    attempt_module_progress.question_order) — this function is never
    called again for the same attempt/module, which is why a plain
    (non-seeded) shuffle is correct here: reproducibility comes from
    storage, not from re-deriving the same random sequence twice.

    Sprint 78 — group_ids is optional and additive. When omitted (every
    pre-Sprint-78 caller, and ModuleExecutionService._create_module_progress()'s
    own call — see that method's docstring for why module-level shuffle
    stays out of scope), behavior is byte-identical to before this
    sprint: shuffle=False returns question_ids as-is, shuffle=True does
    a plain random.shuffle with no group awareness.

    When group_ids IS given (index-aligned with question_ids — the
    i-th entry is the group_id of the i-th question, or None for an
    ungrouped question) and shuffle=True, this instead shuffles whole
    GROUP BLOCKS rather than individual questions: every run of
    questions sharing the same group_id is kept together, in the exact
    relative order they already had in question_ids (the same
    authoritative base order shuffle=False always preserves — no new
    ordering semantics invented, since Question has no order_number
    field and this project's existing convention for "the order
    questions were fetched in" IS the authoritative order), and an
    ungrouped question is its own single-question block. Only the
    block sequence itself is randomized. This guarantees every grouped
    question's shared stimulus/context stays contiguous for the
    student even when the admin has shuffle_questions enabled — a
    non-contiguous group (e.g. A1, B1, A2, B2, A3) is never produced.

    group_ids does NOT depend on whether the referenced QuestionGroup
    row still exists or is soft-deleted — it only groups by the raw
    Question.group_id value, so a soft-deleted group's questions still
    stay contiguous (harmless: Sprint 77's delivery layer independently
    suppresses that group's stimulus_text at display time; keeping
    those questions together is still strictly safer/more consistent
    than letting them scatter, and this function has no reason to query
    QuestionGroup at all)."""
    ordered = list(question_ids)
    if not shuffle:
        return ordered
    if group_ids is None or len(group_ids) != len(question_ids):
        random.shuffle(ordered)
        return ordered

    blocks: list[list[uuid.UUID]] = []
    block_index_by_group: dict[uuid.UUID, int] = {}
    for qid, gid in zip(question_ids, group_ids):
        if gid is None:
            blocks.append([qid])
            continue
        idx = block_index_by_group.get(gid)
        if idx is None:
            block_index_by_group[gid] = len(blocks)
            blocks.append([qid])
        else:
            blocks[idx].append(qid)

    random.shuffle(blocks)
    return [qid for block in blocks for qid in block]
