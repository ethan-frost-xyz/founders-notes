from episode_ids import format_episode_id, make_id, parse_numbered_episode_id


def test_format_episode_id():
    assert format_episode_id(1) == "ep-0001"
    assert format_episode_id(418) == "ep-0418"


def test_parse_numbered_episode_id():
    assert parse_numbered_episode_id("ep-0001") == 1
    assert parse_numbered_episode_id("ep-1") == 1
    assert parse_numbered_episode_id("ep-special-foo") is None


def test_make_id():
    assert make_id(200, "200-james-dyson") == "ep-0200"
    assert make_id(None, "bonus-episode") == "ep-special-bonus-episode"
