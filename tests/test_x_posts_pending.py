from x_posts_pending import append_pending_units, load_pending, remove_pending_ids


def test_pending_dedupe_and_remove(tmp_path, monkeypatch):
    import x_posts_pending as mod

    pending_path = tmp_path / "catalog" / "x-posts-pending.jsonl"
    monkeypatch.setattr(mod, "X_POSTS_PENDING", pending_path)

    unit = {
        "x_post_id": "111",
        "thread_root_id": "111",
        "created_at": "2026-01-01",
        "post_kind": "tweet",
        "text": "hello",
    }
    assert append_pending_units([unit], "2026-06-09T00:00:00Z") == 1
    assert append_pending_units([unit], "2026-06-09T00:00:00Z") == 0
    assert len(load_pending()) == 1

    remove_pending_ids({"111"})
    assert load_pending() == []
