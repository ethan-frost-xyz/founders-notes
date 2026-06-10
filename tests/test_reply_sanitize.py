"""Tests for Librarian reply leak sanitization."""

from __future__ import annotations

from reply_sanitize import sanitize_librarian_reply

_CLEAN = "Rockefeller framed competition as a duty to customers [ep-0016]."


def test_sanitize_preserves_clean_prose():
    assert sanitize_librarian_reply(_CLEAN) == _CLEAN


def test_sanitize_strips_redacted_reasoning_block():
    open_tag = "<" + "redacted_reasoning" + ">"
    close_tag = "</" + "redacted_reasoning" + ">"
    raw = f"{open_tag}\ninternal chain of thought\n{close_tag}\n{_CLEAN}"
    assert sanitize_librarian_reply(raw) == _CLEAN


def test_sanitize_strips_dsml_tags_and_blocks():
    raw = (
        '<DSML invoke="search">tool noise</DSML>'
        f"{_CLEAN}"
        "<DSML>more</DSML>"
    )
    assert sanitize_librarian_reply(raw) == _CLEAN
    assert "DSML" not in sanitize_librarian_reply(raw)


def test_sanitize_empty_after_strip():
    assert sanitize_librarian_reply('<DSML invoke="x">only markup</DSML>') == ""
