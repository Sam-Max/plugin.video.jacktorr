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
        return {"service_host": "localhost", "service_port": "8090"}.get(setting, "0")

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


def _capture_listing(monkeypatch):
    items = []
    add_directory_item = MagicMock()
    monkeypatch.setattr(
        navigation,
        "list_item",
        lambda label, *_args, **_kwargs: items.append((label, MagicMock())) or items[-1][1],
    )
    monkeypatch.setattr(navigation, "addDirectoryItem", add_directory_item)
    return items, add_directory_item


def test_torrents_groups_present_categories_and_keeps_custom_categories(monkeypatch):
    monkeypatch.setattr(
        navigation.api,
        "torrents",
        lambda: [
            {"hash": "one", "category": "Series"},
            {"hash": "two", "category": "Movies"},
            {"hash": "three", "category": "Series"},
            {"hash": "four", "category": "Anime"},
        ],
    )
    monkeypatch.setattr(navigation, "translate", lambda string_id: "Uncategorized")
    items, _add_directory_item = _capture_listing(monkeypatch)

    navigation.torrents()

    assert [label for label, _item in items] == ["Anime", "Movies", "Series"]


def test_torrents_groups_invalid_categories_into_uncategorized(monkeypatch):
    monkeypatch.setattr(
        navigation.api,
        "torrents",
        lambda: [
            {"hash": "missing"},
            {"hash": "none", "category": None},
            {"hash": "empty", "category": ""},
            {"hash": "number", "category": 1},
            {"hash": "custom", "category": "Custom"},
        ],
    )
    monkeypatch.setattr(navigation, "translate", lambda string_id: "Uncategorized")
    items, _add_directory_item = _capture_listing(monkeypatch)

    navigation.torrents()

    assert [label for label, _item in items] == ["Uncategorized", "Custom"]


def test_category_torrents_filters_content_and_preserves_actions(monkeypatch):
    monkeypatch.setattr(
        navigation.api,
        "torrents",
        lambda: [
            {"hash": "show", "title": "Show", "category": "Series", "stat": 3},
            {"hash": "movie", "title": "Movie", "category": "Movies", "stat": 3},
        ],
    )
    torrent_item = MagicMock()
    monkeypatch.setattr(navigation, "list_item", MagicMock(return_value=torrent_item))
    add_directory_item = MagicMock()
    monkeypatch.setattr(navigation, "addDirectoryItem", add_directory_item)
    url_for = MagicMock(return_value="plugin://jacktorr")
    monkeypatch.setattr(navigation.plugin, "url_for", url_for)
    monkeypatch.setattr(navigation.plugin, "args", {"category": ["Series"]})

    navigation.category_torrents()

    add_directory_item.assert_called_once_with(
        navigation.plugin.handle,
        "plugin://jacktorr",
        torrent_item,
        isFolder=True,
    )
    assert any(
        call.args == (navigation.torrent_action, "show", "set_category")
        for call in url_for.call_args_list
    )
    assert any(
        call.args == (navigation.torrent_action, "show", "remove_torrent")
        for call in url_for.call_args_list
    )
    assert all("movie" not in call.args for call in url_for.call_args_list)


def test_category_torrents_includes_all_uncategorized_values(monkeypatch):
    monkeypatch.setattr(
        navigation.api,
        "torrents",
        lambda: [
            {"hash": "missing"},
            {"hash": "none", "category": None},
            {"hash": "empty", "category": ""},
            {"hash": "number", "category": 1},
            {"hash": "series", "category": "Series"},
        ],
    )
    monkeypatch.setattr(navigation, "list_item", lambda *_args, **_kwargs: MagicMock())
    add_directory_item = MagicMock()
    monkeypatch.setattr(navigation, "addDirectoryItem", add_directory_item)

    navigation.uncategorized_torrents()

    assert add_directory_item.call_count == 4


def test_torrent_action_refreshes_after_category_change(monkeypatch):
    dialog = MagicMock()
    dialog.input.return_value = "Series"
    set_torrent = MagicMock()
    refresh = MagicMock()
    monkeypatch.setattr(navigation, "Dialog", lambda: dialog)
    monkeypatch.setattr(navigation.api, "set_torrent", set_torrent)
    monkeypatch.setattr(navigation, "refresh", refresh)

    navigation.torrent_action("hash", "set_category")

    set_torrent.assert_called_once_with("hash", category="Series")
    refresh.assert_called_once_with()


def test_torrent_action_refreshes_after_removal(monkeypatch):
    remove_torrent = MagicMock()
    refresh = MagicMock()
    delete_metadata = MagicMock()
    monkeypatch.setattr(navigation.api, "remove_torrent", remove_torrent)
    monkeypatch.setattr(navigation, "refresh", refresh)
    monkeypatch.setattr(navigation, "delete_display_metadata", delete_metadata)

    navigation.torrent_action("hash", "remove_torrent")

    remove_torrent.assert_called_once_with("hash")
    delete_metadata.assert_not_called()
    refresh.assert_called_once_with()


def test_torrent_item_uses_shared_display_metadata(monkeypatch):
    torrent_item = MagicMock()
    set_info_tag = MagicMock()
    monkeypatch.setattr(navigation, "get_display_metadata", lambda *_args: {
        "title": "Shared", "plot": "Plot", "poster": "Poster"
    })
    monkeypatch.setattr(navigation, "list_item", MagicMock(return_value=torrent_item))
    monkeypatch.setattr(navigation, "set_info_tag", set_info_tag)
    monkeypatch.setattr(navigation, "addDirectoryItem", MagicMock())
    monkeypatch.setattr(navigation.plugin, "url_for", MagicMock(return_value="plugin://jacktorr"))

    navigation.add_torrent_item({"hash": "a" * 40, "title": "Server title", "stat": 0})

    navigation.list_item.assert_called_once_with("Shared", "download.png", poster="Poster")
    set_info_tag.assert_called_once_with(
        torrent_item, "video", {"title": "Shared", "plot": "Plot"}
    )


def test_torrent_item_falls_back_when_shared_metadata_is_missing(monkeypatch):
    torrent_item = MagicMock()
    set_info_tag = MagicMock()
    monkeypatch.setattr(navigation, "get_display_metadata", lambda *_args: {})
    monkeypatch.setattr(navigation, "list_item", MagicMock(return_value=torrent_item))
    monkeypatch.setattr(navigation, "set_info_tag", set_info_tag)
    monkeypatch.setattr(navigation, "addDirectoryItem", MagicMock())
    monkeypatch.setattr(navigation.plugin, "url_for", MagicMock(return_value="plugin://jacktorr"))

    navigation.add_torrent_item({"hash": "a" * 40, "title": "Server title", "poster": "Server poster", "stat": 0})

    navigation.list_item.assert_called_once_with("Server title", "download.png", poster="Server poster")
    set_info_tag.assert_called_once_with(
        torrent_item, "video", {"title": "Server title", "plot": ""}
    )


def test_torrent_action_deletes_metadata_only_after_confirmed_removal(monkeypatch):
    response = MagicMock(status_code=200)
    delete_metadata = MagicMock()
    monkeypatch.setattr(navigation.api, "remove_torrent", MagicMock(return_value=response))
    monkeypatch.setattr(navigation, "delete_display_metadata", delete_metadata)
    monkeypatch.setattr(navigation, "refresh", MagicMock())

    navigation.torrent_action("a" * 40, "remove_torrent")

    delete_metadata.assert_called_once_with(navigation.api._base_url, "a" * 40)
