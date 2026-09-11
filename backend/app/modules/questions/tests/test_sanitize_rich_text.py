"""Sprint 32 — pure sanitizer tests. This file has NO dependency on
QuestionRepository (unlike test_question_service.py), so it is NOT
affected by the pre-existing `list[Question]` collection error
documented since Sprint 20 — it genuinely runs and passes in this
sandbox, unlike most of this module's other tests."""
from app.modules.questions.validators import sanitize_rich_text


def test_plain_text_passes_through_unchanged():
    """Backward compatibility — every question/option written before
    Sprint 32 (plain text, no HTML) must render exactly as before."""
    assert sanitize_rich_text("Oddiy savol matni, HTML yo'q") == "Oddiy savol matni, HTML yo'q"


def test_allowed_formatting_tags_are_preserved():
    result = sanitize_rich_text("<h2>Sarlavha</h2><p>Matn <b>qalin</b> va <i>qiya</i></p><ul><li>band</li></ul>")
    assert "<h2>Sarlavha</h2>" in result
    assert "<b>qalin</b>" in result
    assert "<i>qiya</i>" in result
    assert "<ul><li>band</li></ul>" in result


def test_script_tag_is_stripped():
    result = sanitize_rich_text("<script>alert('xss')</script>Matn")
    assert "<script" not in result
    assert "</script>" not in result


def test_event_handler_attribute_is_stripped():
    result = sanitize_rich_text('<img src=x onerror="alert(1)">Matn')
    assert "onerror" not in result
    assert "<img" not in result  # img isn't on the allowed tags list at all


def test_javascript_protocol_link_is_stripped():
    result = sanitize_rich_text('<a href="javascript:alert(1)">bad link</a>')
    assert "javascript:" not in result


def test_legitimate_https_link_is_preserved():
    result = sanitize_rich_text('<a href="https://example.com">real link</a>')
    assert 'href="https://example.com"' in result


def test_legitimate_http_link_is_preserved():
    result = sanitize_rich_text('<a href="http://example.com">real link</a>')
    assert 'href="http://example.com"' in result


def test_disallowed_tags_like_iframe_are_stripped():
    result = sanitize_rich_text('<iframe src="https://evil.com"></iframe>Text')
    assert "<iframe" not in result


def test_style_attribute_is_never_allowed():
    """No CSSSanitizer is configured (see validators.py's own note) —
    confirms the style attribute is genuinely dropped, not silently
    passed through unsanitized."""
    result = sanitize_rich_text('<p style="background:url(javascript:alert(1))">Text</p>')
    assert "style" not in result
    assert "javascript:" not in result
