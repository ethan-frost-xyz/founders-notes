from unittest.mock import patch

from x_posts_chrono import is_founders_recap_shape, try_chrono_attribution


def _row(num: int) -> dict:
    return {
        "id": f"ep-{num:04d}",
        "episode_number": num,
        "slug": f"{num}-example",
        "title": f"Episode {num}",
    }


def test_is_founders_recap_shape_article():
    assert is_founders_recap_shape(
        {"post_kind": "article", "text": "Founders recap with enough words here for testing"}
    )


def test_is_founders_recap_shape_rejects_short_tweet():
    assert not is_founders_recap_shape({"post_kind": "tweet", "text": "hi there"})


def test_is_founders_recap_shape_rejects_link_only():
    assert not is_founders_recap_shape(
        {"post_kind": "tweet", "text": "https://example.com/foo"}
    )


@patch("x_posts_chrono.vault_has_post", return_value=False)
@patch("x_posts_chrono.last_assigned_post_date", return_value="2026-01-01")
@patch("x_posts_chrono.next_expected_episode", return_value=200)
def test_chrono_assigns_next_episode(mock_next, mock_last, mock_has):
    unit = {
        "text": "A" * 220,
        "post_kind": "tweet",
        "created_at": "2026-02-01",
    }
    by_number = {200: _row(200)}
    row, score, reason = try_chrono_attribution(unit, by_number)
    assert row is not None
    assert row["episode_number"] == 200
    assert score >= 0.9
    assert reason == "chrono_next"


@patch("x_posts_chrono.next_expected_episode", return_value=200)
def test_chrono_blocked_by_different_mention(mock_next):
    unit = {
        "text": "Great episode #198 recap " + "x" * 200,
        "post_kind": "tweet",
        "created_at": "2026-02-01",
    }
    row, score, reason = try_chrono_attribution(unit, {200: _row(200)})
    assert row is None
    assert reason == "chrono_blocked_mention"
