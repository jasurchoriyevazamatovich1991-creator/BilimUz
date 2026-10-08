"""Sprint 80 — QuestionGroupCreateRequest/UpdateRequest.stimulus_text
sanitization. Audit finding (Sprint 80 Phase 1/5): stimulus_text had NO
sanitization field_validator at all before this sprint (unlike
question_text/option_text since Sprint 32, and explanation since
Sprint 32's own dedicated fix) — latent because AttemptPage previously
rendered it as plain JSX, but an active XSS surface the moment it is
routed through FormulaText's dangerouslySetInnerHTML (this same
sprint). Mirrors test_sanitize_rich_text.py's own coverage shape,
exercised through the Pydantic schema boundary rather than the bare
function, since that is the actual security boundary a request crosses.
"""
import uuid

from app.modules.tests.schemas import QuestionGroupCreateRequest, QuestionGroupUpdateRequest


def _create_request(stimulus_text):
    return QuestionGroupCreateRequest(test_id=uuid.uuid4(), title="Passage 1", stimulus_text=stimulus_text)


def test_create_request_strips_script_tag_from_stimulus_text():
    req = _create_request("<script>alert('xss')</script>Matn")
    assert "<script" not in req.stimulus_text
    assert "</script>" not in req.stimulus_text


def test_create_request_strips_event_handler_from_stimulus_text():
    req = _create_request('<img src=x onerror="alert(1)">Matn')
    assert "onerror" not in req.stimulus_text
    assert "<img" not in req.stimulus_text


def test_create_request_strips_javascript_protocol_from_stimulus_text():
    req = _create_request('<a href="javascript:alert(1)">bad link</a>')
    assert "javascript:" not in req.stimulus_text


def test_create_request_preserves_allowed_formatting_tags_in_stimulus_text():
    req = _create_request("<p>Matn <b>qalin</b></p>")
    assert "<b>qalin</b>" in req.stimulus_text


def test_create_request_plain_text_stimulus_unchanged():
    """Backward compatibility — every QuestionGroup written before this
    sprint (plain text, no HTML) must keep rendering exactly as before."""
    req = _create_request("Once upon a time, in a faraway land...")
    assert req.stimulus_text == "Once upon a time, in a faraway land..."


def test_create_request_none_stimulus_stays_none():
    req = _create_request(None)
    assert req.stimulus_text is None


def test_update_request_strips_script_tag_from_stimulus_text():
    req = QuestionGroupUpdateRequest(stimulus_text="<script>alert('xss')</script>Matn")
    assert "<script" not in req.stimulus_text


def test_update_request_none_stimulus_stays_none():
    req = QuestionGroupUpdateRequest(stimulus_text=None)
    assert req.stimulus_text is None


def test_update_request_omitted_stimulus_defaults_to_none():
    req = QuestionGroupUpdateRequest(title="New title")
    assert req.stimulus_text is None
