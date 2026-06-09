from unittest.mock import MagicMock

from x_sync_fetch import fetch_timeline_backfill, fetch_timeline_windowed


def _mock_response(data: list[dict], next_token: str | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": data,
        "meta": {"next_token": next_token} if next_token else {},
    }
    return resp


def test_windowed_stops_on_known_id():
    sess = MagicMock()
    sess.get.return_value = _mock_response(
        [
            {"id": "200", "text": "new"},
            {"id": "100", "text": "old"},
        ]
    )
    tweets, pages = fetch_timeline_windowed(
        sess,
        "token",
        "uid",
        existing_ids={"100"},
        since_id="99",
        initial_window=10,
        max_expansions=3,
    )
    assert pages == 1
    assert [t["id"] for t in tweets] == ["200"]


def test_windowed_passes_since_id_on_first_page():
    sess = MagicMock()
    sess.get.return_value = _mock_response([])
    fetch_timeline_windowed(
        sess,
        "token",
        "uid",
        existing_ids=set(),
        since_id="555",
        initial_window=10,
        max_expansions=0,
    )
    params = sess.get.call_args.kwargs["params"]
    assert params["since_id"] == "555"
    assert params["max_results"] == 10


def test_windowed_respects_max_expansions():
    sess = MagicMock()
    sess.get.side_effect = [
        _mock_response([{"id": "300", "text": "a"}], next_token="p2"),
        _mock_response([{"id": "299", "text": "b"}], next_token="p3"),
        _mock_response([{"id": "298", "text": "c"}], next_token="p4"),
        _mock_response([{"id": "297", "text": "d"}]),
    ]
    tweets, pages = fetch_timeline_windowed(
        sess,
        "token",
        "uid",
        existing_ids=set(),
        initial_window=10,
        max_expansions=2,
    )
    assert pages == 3
    assert len(tweets) == 3
    second_params = sess.get.call_args_list[1].kwargs["params"]
    assert second_params["max_results"] == 15
    assert "since_id" not in second_params


def test_backfill_stops_on_known_id():
    sess = MagicMock()
    sess.get.return_value = _mock_response(
        [{"id": "50", "text": "x"}, {"id": "40", "text": "y"}]
    )
    tweets, pages = fetch_timeline_backfill(
        sess,
        "token",
        "uid",
        max_pages=5,
        existing_ids={"40"},
        incremental=True,
    )
    assert pages == 1
    assert [t["id"] for t in tweets] == ["50"]
