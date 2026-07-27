import pytest

from lib.episode_matching import match_episode_file


def _candidate(path, file_id=1):
    return {"id": file_id, "path": path}


@pytest.mark.parametrize(
    "path",
    [
        "Show.S01E05.1080p.mkv",
        "Show_s1e5_720p.mkv",
        "Show/1x05/title.mkv",
    ],
)
def test_match_episode_file_recognizes_strong_filename_forms(path):
    candidate = _candidate(path)

    assert match_episode_file([candidate], 1, 5) is candidate


@pytest.mark.parametrize(
    "path",
    [
        "Show.S01E050.mkv",
        "Show.1x050.mkv",
    ],
)
def test_match_episode_file_rejects_embedded_larger_episode_numbers(path):
    assert match_episode_file([_candidate(path)], 1, 5) is None


@pytest.mark.parametrize(
    "path",
    [
        "Show.S01E05E06.mkv",
        "Show.S01E05-06.mkv",
        "Show.S01E05-E06.mkv",
        "Show.S01E05-S01E06.mkv",
    ],
)
def test_match_episode_file_rejects_multi_episode_candidates(path):
    assert match_episode_file([_candidate(path)], 1, 5) is None


def test_match_episode_file_accepts_release_suffix_after_episode():
    candidate = _candidate("Show.S01E05-1080p.mkv")

    assert match_episode_file([candidate], 1, 5) is candidate


def test_match_episode_file_prefers_single_episode_over_multi_episode_candidate():
    multi_episode = _candidate("Show.S01E05E06.mkv", 1)
    single_episode = _candidate("Show.S01E05.mkv", 2)

    assert match_episode_file([multi_episode, single_episode], 1, 5) is single_episode


def test_match_episode_file_uses_season_folder_for_episode_only_name():
    candidate = _candidate("Show/Season 1/Episode 5.mkv")

    assert match_episode_file([candidate], 1, 5) is candidate


def test_match_episode_file_uses_torrent_title_for_episode_only_name():
    candidate = _candidate("Show/Ep 5.mkv")

    assert match_episode_file([candidate], 1, 5, torrent_title="Show S01") is candidate


def test_match_episode_file_does_not_select_episode_only_name_without_season_context():
    assert match_episode_file([_candidate("Show/Episode 5.mkv")], 1, 5) is None


def test_match_episode_file_rejects_conflicting_season_context():
    candidate = _candidate("Show/Season 2/Episode 5.mkv")

    assert match_episode_file([candidate], 1, 5, torrent_title="Show Season 1") is None


def test_match_episode_file_returns_none_for_multiple_strong_matches():
    candidates = [_candidate("Show.S01E05.mkv", 1), _candidate("Show.1x05.mkv", 2)]

    assert match_episode_file(candidates, 1, 5) is None


def test_match_episode_file_prefers_one_strong_match_over_weak_alternatives():
    strong = _candidate("Show.S01E05.mkv", 1)
    weak = _candidate("Show/Season 1/Episode 5.mkv", 2)

    assert match_episode_file([strong, weak], 1, 5) is strong
