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
        return "T{}".format(string_id)

    def getSetting(self, setting):
        return {"service_host": "localhost", "service_port": "8090"}.get(
            setting, "0"
        )

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
for _name, _value in {
    "LOGFATAL": 50,
    "LOGERROR": 40,
    "LOGWARNING": 30,
    "LOGINFO": 20,
    "LOGDEBUG": 10,
    "LOGNONE": 0,
}.items():
    setattr(xbmc, _name, getattr(xbmc, _name, _value))

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
    setattr(xbmcgui, name, getattr(xbmcgui, name, _value))

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

from lib import navigation  # noqa: E402

import logging


class _SecretTorrServerError(navigation.TorrServerError):
    """Stands in for TorrServer errors that embed a raw response body
    (potentially carrying indexer credentials) in the message."""

    pass


def _search_route(monkeypatch, results, settings=None, error=None):
    """Wire the search route with a mocked API and notification spy.

    Returns (notifications, settings_probes) lists so tests can assert the
    exact notifications shown and whether the settings probe ran at all.
    """
    notifications = []
    settings_probes = []

    monkeypatch.setattr(navigation, "notification", notifications.append)
    monkeypatch.setattr(
        navigation, "translate", lambda string_id: "T{}".format(string_id)
    )
    monkeypatch.setattr(navigation, "api", MagicMock())
    if error is not None:
        monkeypatch.setattr(
            navigation.api, "search", MagicMock(side_effect=error)
        )
        monkeypatch.setattr(
            navigation.api, "search_torznab", MagicMock(side_effect=error)
        )
    else:
        monkeypatch.setattr(navigation.api, "search", MagicMock(return_value=results))
        monkeypatch.setattr(
            navigation.api, "search_torznab", MagicMock(return_value=results)
        )

    def fake_get_settings():
        settings_probes.append(True)
        if isinstance(settings, Exception):
            raise settings
        return settings

    monkeypatch.setattr(navigation.api, "get_settings", fake_get_settings)
    return notifications, settings_probes


def test_rutor_empty_results_shows_hint_when_rutor_disabled_on_server(monkeypatch):
    notifications, probes = _search_route(
        monkeypatch, results=[], settings={"EnableRutorSearch": False}
    )

    navigation.search_results(query="term")

    assert notifications == ["T30253"]
    assert probes == [True]


def test_rutor_empty_results_show_neutral_message_when_rutor_enabled(monkeypatch):
    notifications, probes = _search_route(
        monkeypatch, results=[], settings={"EnableRutorSearch": True}
    )

    navigation.search_results(query="term")

    assert notifications == ["T30271"]
    assert probes == [True]


def test_rutor_empty_results_show_neutral_message_when_settings_missing(monkeypatch):
    notifications, probes = _search_route(monkeypatch, results=[], settings=None)

    navigation.search_results(query="term")

    assert notifications == ["T30271"]
    assert probes == [True]


def test_rutor_empty_results_show_neutral_message_when_settings_malformed(monkeypatch):
    notifications, probes = _search_route(monkeypatch, results=[], settings=["bad"])

    navigation.search_results(query="term")

    assert notifications == ["T30271"]
    assert probes == [True]


def test_rutor_empty_results_show_neutral_message_when_probe_fails_without_logging_secret(
    monkeypatch, caplog
):
    notifications, probes = _search_route(
        monkeypatch,
        results=[],
        settings=_SecretTorrServerError("probe failed: DUMMY-TORZNAB-KEY"),
    )

    with caplog.at_level(logging.WARNING):
        navigation.search_results(query="term")

    assert notifications == ["T30271"]
    assert probes == [True]
    assert "DUMMY-TORZNAB-KEY" not in caplog.text


def test_rutor_success_renders_playable_items_with_magnet_destination(monkeypatch):
    notifications, probes = _search_route(
        monkeypatch,
        results=[{"Title": "A", "Magnet": "magnet:?xt=urn:btih:x", "Size": "1 GB"}],
        settings=None,
    )

    class RecordingItem:
        def __init__(self, label, *args, **kwargs):
            self.label = label
            self.properties = {}
            self.context_items = None

        def setProperty(self, key, value):
            self.properties[key] = value

        def addContextMenuItems(self, items):
            self.context_items = items

    added = MagicMock()
    monkeypatch.setattr(navigation, "addDirectoryItem", added)
    monkeypatch.setattr(navigation, "list_item", RecordingItem)
    monkeypatch.setattr(
        navigation.plugin,
        "url_for",
        lambda func, **kwargs: "plugin://play_magnet?magnet={}".format(
            kwargs.get("magnet")
        ),
    )

    navigation.search_results(query="term")

    assert probes == []
    assert notifications == []
    assert added.call_count == 1
    args, kwargs = added.call_args
    item = args[2]
    assert item.label == "A (1 GB)"
    assert item.properties["IsPlayable"] == "true"
    assert args[1] == "plugin://play_magnet?magnet=magnet:?xt=urn:btih:x"
    assert kwargs["isFolder"] is False
    assert item.context_items[0][0] == "T30254"
    assert item.context_items[0][1] == "PlayMedia(plugin://play_magnet?magnet=magnet:?xt=urn:btih:x)"


def test_torznab_success_renders_playable_items_with_magnet_destination(monkeypatch):
    notifications, probes = _search_route(
        monkeypatch,
        results=[{"Title": "A", "Magnet": "magnet:?xt=urn:btih:x", "Size": "1 GB"}],
        settings=None,
    )

    class RecordingItem:
        def __init__(self, label, *args, **kwargs):
            self.label = label
            self.properties = {}
            self.context_items = None

        def setProperty(self, key, value):
            self.properties[key] = value

        def addContextMenuItems(self, items):
            self.context_items = items

    added = MagicMock()
    monkeypatch.setattr(navigation, "addDirectoryItem", added)
    monkeypatch.setattr(navigation, "list_item", RecordingItem)
    monkeypatch.setattr(
        navigation.plugin,
        "url_for",
        lambda func, **kwargs: "plugin://play_magnet?magnet={}".format(
            kwargs.get("magnet")
        ),
    )

    navigation.torznab_search_results(query="term")

    assert probes == []
    assert notifications == []
    assert added.call_count == 1
    args, kwargs = added.call_args
    item = args[2]
    assert item.label == "A (1 GB)"
    assert item.properties["IsPlayable"] == "true"
    assert args[1] == "plugin://play_magnet?magnet=magnet:?xt=urn:btih:x"
    assert kwargs["isFolder"] is False


def test_rutor_success_never_probes_server_settings(monkeypatch):
    notifications, probes = _search_route(
        monkeypatch,
        results=[{"Title": "A", "Magnet": "magnet:?xt=urn:btih:x", "Size": "1 GB"}],
        settings=None,
    )
    added = MagicMock()
    monkeypatch.setattr(navigation, "addDirectoryItem", added)

    navigation.search_results(query="term")

    assert probes == []
    assert notifications == []
    assert added.call_count == 1


def test_torznab_empty_results_shows_hint_when_torznab_disabled_on_server(monkeypatch):
    notifications, probes = _search_route(
        monkeypatch, results=[], settings={"EnableTorznabSearch": False}
    )

    navigation.torznab_search_results(query="term")

    assert notifications == ["T30262"]
    assert probes == [True]


def test_torznab_empty_results_show_neutral_message_when_torznab_enabled(monkeypatch):
    notifications, probes = _search_route(
        monkeypatch, results=[], settings={"EnableTorznabSearch": True}
    )

    navigation.torznab_search_results(query="term")

    assert notifications == ["T30271"]
    assert probes == [True]


def test_torznab_empty_results_show_neutral_message_when_probe_fails_without_logging_secret(
    monkeypatch, caplog
):
    notifications, probes = _search_route(
        monkeypatch,
        results=[],
        settings=_SecretTorrServerError("probe failed: DUMMY-TORZNAB-KEY"),
    )

    with caplog.at_level(logging.WARNING):
        navigation.torznab_search_results(query="term")

    assert notifications == ["T30271"]
    assert probes == [True]
    assert "DUMMY-TORZNAB-KEY" not in caplog.text


def test_torznab_empty_results_show_neutral_message_when_settings_malformed(monkeypatch):
    notifications, probes = _search_route(monkeypatch, results=[], settings="oops")

    navigation.torznab_search_results(query="term")

    assert notifications == ["T30271"]
    assert probes == [True]


def test_torznab_success_never_probes_server_settings(monkeypatch):
    notifications, probes = _search_route(
        monkeypatch,
        results=[{"Title": "A", "Magnet": "magnet:?xt=urn:btih:x", "Size": "1 GB"}],
        settings=None,
    )
    added = MagicMock()
    monkeypatch.setattr(navigation, "addDirectoryItem", added)

    navigation.torznab_search_results(query="term")

    assert probes == []
    assert notifications == []
    assert added.call_count == 1


def test_search_error_route_does_not_probe_settings(monkeypatch):
    notifications, probes = _search_route(
        monkeypatch, results=[], error=navigation.TorrServerError("boom")
    )

    navigation.search_results(query="term")

    assert notifications == ["boom"]
    assert probes == []
