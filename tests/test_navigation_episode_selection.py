import sys
import types
from unittest.mock import MagicMock, call


class _Addon:
    def getAddonInfo(self, key):
        return {
            "name": "JackTorr",
            "id": "plugin.video.jacktorr",
            "path": ".",
            "icon": "",
            "profile": ".",
        }[key]

    def getLocalizedString(self, string_id):
        return str(string_id)

    def getSetting(self, setting):
        return {
            "service_host": "localhost",
            "service_port": "8090",
            "min_candidate_size": "0",
        }.get(setting, "0")

    def setSetting(self, _setting, _value):
        return None

    def openSettings(self):
        return None


class _Dummy:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


xbmc = sys.modules.setdefault("xbmc", types.ModuleType("xbmc"))
xbmc.Monitor = getattr(xbmc, "Monitor", _Dummy)
xbmc.Player = getattr(xbmc, "Player", _Dummy)
xbmc.executebuiltin = getattr(xbmc, "executebuiltin", lambda _command: None)
xbmc.getInfoLabel = getattr(xbmc, "getInfoLabel", lambda _label: "")
xbmc.getCondVisibility = getattr(xbmc, "getCondVisibility", lambda _condition: False)
xbmc.sleep = getattr(xbmc, "sleep", lambda _milliseconds: None)
xbmc.log = getattr(xbmc, "log", lambda *args, **kwargs: None)
for name, value in {
    "LOGFATAL": 50,
    "LOGERROR": 40,
    "LOGWARNING": 30,
    "LOGINFO": 20,
    "LOGDEBUG": 10,
    "LOGNONE": 0,
}.items():
    setattr(xbmc, name, getattr(xbmc, name, value))

xbmcgui = sys.modules.setdefault("xbmcgui", types.ModuleType("xbmcgui"))
for name in (
    "ListItem",
    "DialogProgress",
    "Dialog",
    "WindowXMLDialog",
    "Window",
    "ControlImage",
    "ControlLabel",
):
    setattr(xbmcgui, name, getattr(xbmcgui, name, _Dummy))
for name, value in {
    "ACTION_PARENT_DIR": 9,
    "ACTION_NAV_BACK": 10,
    "ACTION_PREVIOUS_MENU": 11,
}.items():
    setattr(xbmcgui, name, getattr(xbmcgui, name, value))

xbmcaddon = sys.modules.setdefault("xbmcaddon", types.ModuleType("xbmcaddon"))
xbmcaddon.Addon = _Addon
xbmcvfs = sys.modules.setdefault("xbmcvfs", types.ModuleType("xbmcvfs"))
xbmcvfs.translatePath = lambda path: path

xbmcplugin = sys.modules.setdefault("xbmcplugin", types.ModuleType("xbmcplugin"))
xbmcplugin.addDirectoryItem = lambda *args, **kwargs: None
xbmcplugin.endOfDirectory = lambda *args, **kwargs: None
xbmcplugin.setResolvedUrl = lambda *args, **kwargs: None

routing = sys.modules.setdefault("routing", types.ModuleType("routing"))


class _Plugin:
    handle = 1
    args = {}

    def route(self, _path):
        return lambda function: function

    def url_for(self, *_args, **_kwargs):
        return ""


routing.Plugin = _Plugin

import pytest

from lib import navigation


def test_play_magnet_forwards_episode_metadata_to_play_info_hash(monkeypatch):
    add_magnet = MagicMock(return_value="hash")
    monkeypatch.setattr(navigation.api, "add_magnet", add_magnet)
    play_info_hash = MagicMock()
    monkeypatch.setattr(navigation, "play_info_hash", play_info_hash)

    navigation.play_magnet(
        magnet="magnet:?xt=urn:btih:abc",
        buffer=False,
        poster="poster",
        title="Localized title",
        description="Localized description",
        category="tv",
        season="1",
        episode="5",
    )

    play_info_hash.assert_called_once_with(
        info_hash="hash",
        buffer=False,
        title="Localized title",
        description="Localized description",
        season="1",
        episode="5",
    )
    add_magnet.assert_called_once_with(
        "magnet:?xt=urn:btih:abc", title="Localized title", poster="poster", category="tv"
    )


def test_play_magnet_persists_display_metadata(monkeypatch):
    monkeypatch.setattr(navigation.api, "add_magnet", MagicMock(return_value="a" * 40))
    save_metadata = MagicMock()
    monkeypatch.setattr(navigation, "save_display_metadata", save_metadata)
    monkeypatch.setattr(navigation, "play_info_hash", MagicMock())

    navigation.play_magnet(
        magnet="magnet:?xt=urn:btih:abc", title="Localized title", description="Plot", poster="poster"
    )

    save_metadata.assert_called_once_with(
        navigation.api._base_url, "a" * 40, title="Localized title", plot="Plot", poster="poster"
    )


def test_play_magnet_persists_before_and_after_a_known_hash(monkeypatch):
    info_hash = "a" * 40
    monkeypatch.setattr(navigation.api, "add_magnet", MagicMock(return_value=info_hash))
    save_metadata = MagicMock()
    monkeypatch.setattr(navigation, "save_display_metadata", save_metadata)
    monkeypatch.setattr(navigation, "play_info_hash", MagicMock())

    navigation.play_magnet(
        magnet="magnet:?xt=urn:btih:{}".format(info_hash), title="Localized title", description="Plot", poster="poster"
    )

    assert save_metadata.call_args_list == [
        call(navigation.api._base_url, info_hash, title="Localized title", plot="Plot", poster="poster"),
        call(navigation.api._base_url, info_hash, title="Localized title", plot="Plot", poster="poster"),
    ]


def test_play_url_forwards_episode_metadata_to_play_info_hash(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value = response
    monkeypatch.setattr(navigation.requests, "get", lambda *_args, **_kwargs: response)
    add_torrent_obj = MagicMock(return_value="hash")
    monkeypatch.setattr(navigation.api, "add_torrent_obj", add_torrent_obj)
    play_info_hash = MagicMock()
    monkeypatch.setattr(navigation, "play_info_hash", play_info_hash)

    navigation.play_url(
        url="https://example.com/show.torrent",
        buffer=False,
        poster="poster",
        title="Localized title",
        description="Localized description",
        category="movie",
        season="1",
        episode="5",
    )

    play_info_hash.assert_called_once_with(
        info_hash="hash",
        buffer=False,
        title="Localized title",
        description="Localized description",
        season="1",
        episode="5",
    )
    add_torrent_obj.assert_called_once_with(
        response.raw, title="Localized title", poster="poster", category="movie"
    )


def test_play_uses_metadata_for_list_item_and_video_info_tag(monkeypatch):
    monkeypatch.setattr(navigation, "get_external_subtitles", lambda *_args: [])
    item = MagicMock()
    tag = MagicMock()
    item.getVideoInfoTag.return_value = tag
    list_item = MagicMock(return_value=item)
    player = MagicMock()
    player.__enter__.return_value = player
    monkeypatch.setattr(navigation, "ListItem", list_item)
    monkeypatch.setattr(navigation, "JackTorrPlayer", MagicMock(return_value=player))
    monkeypatch.setattr(navigation, "setResolvedUrl", MagicMock())
    monkeypatch.setattr(navigation, "show_status_overlay", lambda: False)
    monkeypatch.setattr(
        navigation.api, "get_stream_url", lambda **_kwargs: "http://stream.example/video"
    )

    navigation.play(
        info_hash="hash",
        file_id=1,
        path="release.mkv",
        poster="poster.jpg",
        title="Localized title",
        description="Localized description",
    )

    list_item.assert_called_once_with("Localized title", path="http://stream.example/video")
    item.setArt.assert_called_once_with({"poster": "poster.jpg"})
    tag.setTitle.assert_called_once_with("Localized title")
    tag.setPlot.assert_called_once_with("Localized description")


@pytest.mark.parametrize("failed_endpoint", ["info", "playlist", None])
def test_play_resolves_when_subtitle_requests_timeout(monkeypatch, failed_endpoint):
    from requests.exceptions import Timeout

    item = MagicMock()
    player = MagicMock()
    player.__enter__.return_value = player
    resolved = MagicMock()
    subtitle = "http://server/Movie.srt?index=2"
    info = MagicMock(return_value={"name": "Movie"})
    playlist = MagicMock(return_value=(
        "#EXTM3U\n#EXTVLCOPT:input-slave=" + subtitle
        + "#\nhttp://server/Movie.mkv?index=1\n"
    ))
    if failed_endpoint == "info":
        info.side_effect = Timeout("subtitle metadata timed out")
    elif failed_endpoint == "playlist":
        playlist.side_effect = Timeout("subtitle playlist timed out")
    monkeypatch.setattr(navigation.api, "get_torrent_info", info)
    monkeypatch.setattr(navigation.api, "get_playlist", playlist)
    monkeypatch.setattr(navigation.api, "get_stream_url", lambda **_kwargs: "http://video")
    monkeypatch.setattr(navigation, "ListItem", MagicMock(return_value=item))
    monkeypatch.setattr(navigation, "JackTorrPlayer", MagicMock(return_value=player))
    monkeypatch.setattr(navigation, "show_status_overlay", lambda: False)
    monkeypatch.setattr(navigation, "setResolvedUrl", resolved)

    navigation.play(info_hash="abc", file_id=1, path="Movie.mkv")

    info.assert_called_once_with("abc", timeout=5)
    resolved.assert_called_once_with(navigation.plugin.handle, True, item)
    if failed_endpoint:
        item.setSubtitles.assert_not_called()
    else:
        item.setSubtitles.assert_called_once_with([subtitle])
    if failed_endpoint == "info":
        playlist.assert_not_called()


def _run_play_info_hash(monkeypatch, files, dialog_index=0, **metadata):
    info = {"file_stats": files, "title": "Show Season 1"}
    api = navigation.api
    monkeypatch.setattr(api, "get_torrent_info", lambda _info_hash: info)
    monkeypatch.setattr(navigation, "get_min_candidate_size", lambda: 0)
    monkeypatch.setattr(navigation, "is_video", lambda _path: True)
    monkeypatch.setattr(navigation, "sort_files", MagicMock())
    dialog = MagicMock()
    dialog.select.return_value = dialog_index
    monkeypatch.setattr(navigation, "Dialog", lambda: dialog)
    play = MagicMock()
    monkeypatch.setattr(navigation, "play", play)

    navigation.play_info_hash(
        info_hash="hash",
        buffer=False,
        **metadata,
    )
    return dialog, play


def test_play_info_hash_plays_unique_episode_match_without_dialog(monkeypatch):
    files = [
        {"id": 5, "path": "Show.S01E05.mkv", "length": 10},
        {"id": 6, "path": "Show.S01E06.mkv", "length": 10},
    ]

    dialog, play = _run_play_info_hash(monkeypatch, files, season="1", episode="5")

    dialog.select.assert_not_called()
    play.assert_called_once_with(info_hash="hash", file_id=5, path="Show.S01E05.mkv")


def test_play_info_hash_opens_dialog_when_episode_match_is_absent(monkeypatch):
    files = [
        {"id": 4, "path": "Show.S01E04.mkv", "length": 10},
        {"id": 6, "path": "Show.S01E06.mkv", "length": 10},
    ]

    dialog, play = _run_play_info_hash(monkeypatch, files, season="1", episode="5")

    dialog.select.assert_called_once()
    play.assert_called_once_with(info_hash="hash", file_id=4, path="Show.S01E04.mkv")


def test_play_info_hash_opens_dialog_when_episode_match_is_ambiguous(monkeypatch):
    files = [
        {"id": 1, "path": "release-a.S01E05.mkv", "length": 10},
        {"id": 2, "path": "release-b.1x05.mkv", "length": 10},
        {"id": 6, "path": "Show.S01E06.mkv", "length": 10},
    ]

    dialog, play = _run_play_info_hash(
        monkeypatch,
        files,
        dialog_index=1,
        season="1",
        episode="5",
    )

    dialog.select.assert_called_once()
    play.assert_called_once_with(info_hash="hash", file_id=2, path="release-b.1x05.mkv")


def test_torrent_files_uses_original_path_for_stream_url(monkeypatch):
    path = "Show/Season 1/ep01.mkv"
    monkeypatch.setattr(
        navigation.api,
        "get_torrent_info",
        lambda **_kwargs: {"file_stats": [{"id": 7, "path": path}], "title": "Show"},
    )
    stream_url = MagicMock(return_value="http://stream")
    monkeypatch.setattr(navigation.api, "get_stream_url", stream_url)
    monkeypatch.setattr(navigation, "hide_subfolder_components", lambda: True)
    monkeypatch.setattr(navigation, "list_item", lambda *_args, **_kwargs: MagicMock())
    monkeypatch.setattr(navigation, "addDirectoryItem", lambda *_args, **_kwargs: None)

    navigation.torrent_files("hash")

    stream_url.assert_called_once_with(link="hash", path=path, file_id=7)


def test_torrent_files_uses_shared_display_plot_and_falls_back_without_metadata(monkeypatch):
    item = MagicMock()
    set_info_tag = MagicMock()
    monkeypatch.setattr(
        navigation.api,
        "get_torrent_info",
        lambda **_kwargs: {"file_stats": [{"id": 7, "path": "movie.mkv"}], "title": "Server title", "poster": "Server poster"},
    )
    monkeypatch.setattr(navigation.api, "get_stream_url", lambda **_kwargs: "http://stream")
    monkeypatch.setattr(navigation, "list_item", MagicMock(return_value=item))
    monkeypatch.setattr(navigation, "set_info_tag", set_info_tag)
    monkeypatch.setattr(navigation, "get_display_metadata", lambda *_args: {
        "title": "Shared", "plot": "Plot", "poster": "Poster"
    })
    monkeypatch.setattr(navigation, "addDirectoryItem", MagicMock())

    navigation.torrent_files("a" * 40)

    navigation.list_item.assert_called_once_with("movie.mkv", "download.png", poster="Poster")
    set_info_tag.assert_called_once_with(item, "video", {"title": "Shared", "plot": "Plot"})
