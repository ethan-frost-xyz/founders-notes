from x_posts_threads import (
    assemble_threads,
    filter_attributable_rows,
    is_article_unit,
    is_reply_to_other,
)


def test_is_reply_to_other_when_replying_to_someone_else():
    row = {
        "post_kind": "reply",
        "in_reply_to_user_id": "999",
        "x_post_id": "1",
    }
    assert is_reply_to_other(row, "111") is True
    assert is_reply_to_other(row, "999") is False


def test_is_reply_to_other_non_reply():
    row = {"post_kind": "tweet", "in_reply_to_user_id": "999", "x_post_id": "1"}
    assert is_reply_to_other(row, "111") is False


def test_filter_attributable_rows_drops_other_replies():
    rows = [
        {"x_post_id": "1", "post_kind": "tweet", "in_reply_to_user_id": ""},
        {
            "x_post_id": "2",
            "post_kind": "reply",
            "in_reply_to_user_id": "other-user",
        },
    ]
    filtered = filter_attributable_rows(rows, user_id="me")
    assert len(filtered) == 1
    assert filtered[0]["x_post_id"] == "1"


def test_assemble_threads_merges_self_thread_parts():
    rows = [
        {
            "x_post_id": "100",
            "thread_root_id": "100",
            "is_thread_root": "true",
            "post_kind": "tweet",
            "in_reply_to_user_id": "",
            "created_at": "2026-01-01T10:00:00Z",
            "text": "Part one",
            "conversation_id": "100",
        },
        {
            "x_post_id": "101",
            "thread_root_id": "100",
            "is_thread_root": "false",
            "post_kind": "reply",
            "in_reply_to_user_id": "me",
            "created_at": "2026-01-01T10:01:00Z",
            "text": "Part two",
            "conversation_id": "100",
        },
    ]
    units = assemble_threads(rows, user_id="me", attributable_only=True)
    assert len(units) == 1
    assert units[0]["x_post_id"] == "100"
    assert "Part one" in units[0]["text"]
    assert "Part two" in units[0]["text"]
    assert units[0]["part_ids"] == ["100", "101"]


def test_is_article_unit():
    assert is_article_unit({"post_kind": "article", "x_post_id": "1"}) is True
    assert is_article_unit({"post_kind": "tweet", "x_post_id": "1"}) is False
    assert is_article_unit({"x_post_id": "1"}) is False
