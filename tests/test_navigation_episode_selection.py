import sys
import types
from unittest.mock import MagicMock


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

from lib import navigation


def test_play_magnet_forwards_episode_metadata_to_play_info_hash(monkeypatch):
    monkeypatch.setattr(navigation.api, "add_magnet", lambda *_args, **_kwargs: "hash")
    play_info_hash = MagicMock()
    monkeypatch.setattr(navigation, "play_info_hash", play_info_hash)

    navigation.play_magnet(
        magnet="magnet:?xt=urn:btih:abc",
        buffer=False,
        poster="poster",
        season="1",
        episode="5",
    )

    play_info_hash.assert_called_once_with(
        info_hash="hash", buffer=False, season="1", episode="5"
    )


def test_play_url_forwards_episode_metadata_to_play_info_hash(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value = response
    monkeypatch.setattr(navigation.requests, "get", lambda *_args, **_kwargs: response)
    monkeypatch.setattr(
        navigation.api, "add_torrent_obj", lambda *_args, **_kwargs: "hash"
    )
    play_info_hash = MagicMock()
    monkeypatch.setattr(navigation, "play_info_hash", play_info_hash)

    navigation.play_url(
        url="https://example.com/show.torrent",
        buffer=False,
        poster="poster",
        season="1",
        episode="5",
    )

    play_info_hash.assert_called_once_with(
        info_hash="hash", buffer=False, season="1", episode="5"
    )


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
