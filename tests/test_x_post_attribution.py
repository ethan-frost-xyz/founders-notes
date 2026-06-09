from unittest.mock import patch

from x_post_attribution import classify_unit, process_units


def _row(num: int, title: str = "Example Founder Biography") -> dict:
    return {
        "id": f"ep-{num:04d}",
        "episode_number": num,
        "slug": f"{num}-example",
        "title": title,
        "published_at": "2026-01-15",
    }


def test_classify_explicit_mention_first():
    by_number = {131: _row(131)}
    unit = {"text": "Founders ep. 131 recap", "created_at": "2026-02-27", "post_kind": "tweet"}
    outcome = classify_unit(unit, by_number)
    assert outcome.action == "founders"
    assert outcome.row["episode_number"] == 131
    assert outcome.reason == "explicit_mention_131"


@patch("x_post_attribution.post_file_path")
@patch("x_posts_chrono.vault_has_post", return_value=False)
@patch("x_posts_chrono.last_assigned_post_date", return_value="2026-01-01")
@patch("x_posts_chrono.next_expected_episode", return_value=200)
def test_classify_chrono_before_fuzzy(mock_next, mock_last, mock_has, mock_path):
    mock_path.return_value.exists.return_value = False
    by_number = {200: _row(200)}
    unit = {
        "text": "Long founders recap without hash " + "word " * 50,
        "created_at": "2026-02-01",
        "post_kind": "tweet",
        "x_post_id": "1",
    }
    outcome = classify_unit(unit, by_number)
    assert outcome.action == "founders"
    assert outcome.reason == "chrono_next"


@patch("x_post_attribution.write_founders_post")
@patch("x_post_attribution.regenerate_corpus")
@patch("x_post_attribution.save_review_records")
@patch("x_post_attribution.post_file_path")
def test_process_units_dry_run(mock_path, mock_save, mock_corpus, mock_write):
    mock_path.return_value.exists.return_value = False
    by_number = {50: _row(50)}
    units = [
        {
            "text": "#50 great episode",
            "created_at": "2026-01-10",
            "post_kind": "tweet",
            "x_post_id": "99",
        }
    ]
    with patch("x_post_attribution.load_catalog", return_value=list(by_number.values())):
        with patch("x_post_attribution.catalog_by_number", return_value=by_number):
            stats, review, processed = process_units(units, dry_run=True)
    assert stats.mapped == 1
    assert "99" in processed
    mock_write.assert_not_called()
