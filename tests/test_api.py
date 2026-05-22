"""Tests for Jacktorr TorrServer API client.

Regression tests for issue #193: TorrServer may return a JSON list
instead of a dict, causing TypeError when accessing ["hash"].
"""

import json
from unittest.mock import MagicMock, patch, mock_open

import pytest

from lib.torrserver.api import TorrServer, TorrServerError


def _make_response(json_data, status_code=200, text=None):
    """Create a mock requests.Response with the given json data and status code."""
    response = MagicMock()
    response.json.return_value = json_data
    response.status_code = status_code
    response.text = text or json.dumps(json_data)
    return response


@pytest.fixture
def torrserver():
    """Create a TorrServer instance with a mock session."""
    session = MagicMock()
    return TorrServer(
        host="localhost",
        port=8090,
        username="admin",
        password="pass",
        ssl_enabled=False,
        session=session,
    )


class TestParseJsonResponse:
    """Tests for TorrServer._parse_json_response."""

    def test_dict_response_passthrough(self, torrserver):
        """Dict responses pass through unchanged."""
        response = _make_response({"hash": "abc123", "stat": 3})
        result = torrserver._parse_json_response(response, "/torrent/upload")
        assert result == {"hash": "abc123", "stat": 3}

    def test_list_with_one_element_unwrapped(self, torrserver):
        """A single-element list is unwrapped to its first element."""
        response = _make_response([{"hash": "abc123", "stat": 3}])
        result = torrserver._parse_json_response(response, "/torrent/upload")
        assert result == {"hash": "abc123", "stat": 3}

    def test_list_with_multiple_elements_takes_first(self, torrserver):
        """A multi-element list takes only the first element."""
        response = _make_response([{"hash": "first"}, {"hash": "second"}])
        result = torrserver._parse_json_response(response, "/torrent/upload")
        assert result == {"hash": "first"}

    def test_empty_list_raises_error(self, torrserver):
        """An empty list raises TorrServerError."""
        response = _make_response([])
        with pytest.raises(TorrServerError, match="empty list"):
            torrserver._parse_json_response(response, "/torrent/upload")

    def test_non_200_status_raises_error(self, torrserver):
        """HTTP 500 raises TorrServerError with endpoint info."""
        response = _make_response({"error": "internal"}, status_code=500)
        with pytest.raises(TorrServerError, match="/torrent/upload.*HTTP 500"):
            torrserver._parse_json_response(response, "/torrent/upload")

    def test_invalid_json_raises_error(self, torrserver):
        """Invalid JSON raises TorrServerError."""
        response = MagicMock()
        response.status_code = 200
        response.text = "not json"
        response.json.side_effect = ValueError("invalid json")
        with pytest.raises(TorrServerError, match="invalid JSON"):
            torrserver._parse_json_response(response, "/torrent/upload")


class TestAddMagnet:
    """Tests for TorrServer.add_magnet with normalized responses."""

    def test_add_magnet_dict_response(self, torrserver):
        """add_magnet handles standard dict response."""
        torrserver._session.request.return_value = _make_response(
            {"hash": "magnet_hash_1"}
        )
        result = torrserver.add_magnet("magnet:?xt=urn:btih:abc123", title="Test")
        assert result == "magnet_hash_1"

    def test_add_magnet_list_response(self, torrserver):
        """add_magnet handles list response from TorrServer (issue #193)."""
        torrserver._session.request.return_value = _make_response(
            [{"hash": "magnet_hash_1"}]
        )
        result = torrserver.add_magnet("magnet:?xt=urn:btih:abc123", title="Test")
        assert result == "magnet_hash_1"


class TestAddTorrentObj:
    """Tests for TorrServer.add_torrent_obj with normalized responses."""

    def test_add_torrent_obj_dict_response(self, torrserver):
        """add_torrent_obj handles standard dict response."""
        torrserver._session.request.return_value = _make_response(
            {"hash": "torrent_hash_1"}
        )
        mock_file = MagicMock()
        result = torrserver.add_torrent_obj(mock_file)
        assert result == "torrent_hash_1"

    def test_add_torrent_obj_list_response(self, torrserver):
        """add_torrent_obj handles list response (issue #193)."""
        torrserver._session.request.return_value = _make_response(
            [{"hash": "torrent_hash_1"}]
        )
        mock_file = MagicMock()
        result = torrserver.add_torrent_obj(mock_file)
        assert result == "torrent_hash_1"

    def test_add_torrent_obj_empty_list_raises_error(self, torrserver):
        """add_torrent_obj raises error on empty list."""
        torrserver._session.request.return_value = _make_response([])
        mock_file = MagicMock()
        with pytest.raises(TorrServerError):
            torrserver.add_torrent_obj(mock_file)


class TestAddTorrent:
    """Tests for TorrServer.add_torrent with normalized responses."""

    def test_add_torrent_dict_response(self, torrserver, tmp_path):
        """add_torrent handles standard dict response."""
        torrserver._session.request.return_value = _make_response(
            {"hash": "file_hash_1"}
        )
        torrent_file = tmp_path / "test.torrent"
        torrent_file.write_bytes(b"d8:announce17:http://test.com4:info6:teste")
        result = torrserver.add_torrent(str(torrent_file))
        assert result == "file_hash_1"

    def test_add_torrent_list_response(self, torrserver, tmp_path):
        """add_torrent handles list response (issue #193)."""
        torrserver._session.request.return_value = _make_response(
            [{"hash": "file_hash_1"}]
        )
        torrent_file = tmp_path / "test.torrent"
        torrent_file.write_bytes(b"d8:announce17:http://test.com4:info6:teste")
        result = torrserver.add_torrent(str(torrent_file))
        assert result == "file_hash_1"


class TestGetTorrentInfo:
    """Tests for TorrServer info methods with normalized responses."""

    def test_get_torrent_info_dict(self, torrserver):
        """get_torrent_info handles dict response."""
        expected = {"hash": "abc123", "stat": 3, "file_stats": []}
        torrserver._session.request.return_value = _make_response(expected)
        result = torrserver.get_torrent_info("abc123")
        assert result == expected

    def test_get_torrent_info_list(self, torrserver):
        """get_torrent_info handles list response (defensive)."""
        expected_inner = {"hash": "abc123", "stat": 3, "file_stats": []}
        torrserver._session.request.return_value = _make_response([expected_inner])
        result = torrserver.get_torrent_info("abc123")
        assert result == expected_inner

    def test_torrents_dict(self, torrserver):
        """torrents() handles dict response."""
        expected = {"torrents": []}
        torrserver._session.request.return_value = _make_response(expected)
        result = torrserver.torrents()
        assert result == expected

    def test_torrents_list(self, torrserver):
        """torrents() returns raw list from the list endpoint."""
        expected = [{"hash": "abc123"}]
        torrserver._session.request.return_value = _make_response(expected)
        result = torrserver.torrents()
        assert result == expected

    def test_torrents_empty_list(self, torrserver):
        """torrents() handles empty list gracefully (no TorrServerError)."""
        torrserver._session.request.return_value = _make_response([])
        result = torrserver.torrents()
        assert result == []

    def test_get_torrent_info_by_hash_dict(self, torrserver):
        """get_torrent_info_by_hash handles dict response."""
        expected = {"hash": "abc123", "stat": 3}
        torrserver._session.request.return_value = _make_response(expected)
        result = torrserver.get_torrent_info_by_hash("abc123")
        assert result == expected

    def test_get_torrent_info_by_hash_list(self, torrserver):
        """get_torrent_info_by_hash handles list response (defensive)."""
        expected_inner = {"hash": "abc123", "stat": 3}
        torrserver._session.request.return_value = _make_response([expected_inner])
        result = torrserver.get_torrent_info_by_hash("abc123")
        assert result == expected_inner