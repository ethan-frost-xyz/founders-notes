from x_posts_match import match_episode


def _row(num: int, title: str, published_at: str = "2026-01-15") -> dict:
    return {
        "id": f"ep-{num:04d}",
        "episode_number": num,
        "slug": f"{num}-example",
        "title": title,
        "published_at": published_at,
    }


def test_explicit_mention_episode_131():
    by_number = {131: _row(131, "Example Founder Biography")}
    row, score, reason = match_episode(
        "@founderspodcast ep. 131 — great episode",
        "2026-02-27",
        by_number,
    )
    assert row is not None
    assert row["episode_number"] == 131
    assert score >= 0.95
    assert reason == "explicit_mention_131"


def test_explicit_mention_hash_form():
    by_number = {200: _row(200, "Some Title")}
    row, score, reason = match_episode("Check out #200 today", None, by_number)
    assert row is not None
    assert row["episode_number"] == 200
    assert score >= 0.95
    assert reason == "explicit_mention_200"


def test_title_token_fuzzy_match():
    by_number = {
        60: _row(60, "Warren Buffett and Charlie Munger Partnership"),
    }
    text = "warren buffett charlie munger partnership lessons from the episode"
    row, score, reason = match_episode(text, "2026-01-10", by_number)
    assert row is not None
    assert row["episode_number"] == 60
    assert score >= 0.5
    assert reason.startswith("title_tokens_")


def test_no_match():
    by_number = {1: _row(1, "Totally Unrelated Topic Here")}
    row, score, reason = match_episode("hello world random text", None, by_number)
    assert row is None
    assert score == 0.0
    assert reason == "none"
