from unittest.mock import MagicMock

import json
import sys
import types


class _Addon:
    def getAddonInfo(self, key):
        return {
            "name": "JackTorr",
            "id": "plugin.video.jacktorr",
            "path": ".",
            "icon": "",
            "profile": "",
        }[key]

    def getLocalizedString(self, string_id):
        return str(string_id)

    def getSetting(self, _setting):
        return ""

    def setSetting(self, _setting, _value):
        return None

    def openSettings(self):
        return None


xbmc = types.ModuleType("xbmc")
xbmc.Monitor = type("Monitor", (), {"__init__": lambda self: None})
xbmc.executebuiltin = lambda _command: None
xbmc.LOGFATAL = 50
xbmc.LOGERROR = 40
xbmc.LOGWARNING = 30
xbmc.LOGINFO = 20
xbmc.LOGDEBUG = 10
xbmc.LOGNONE = 0

xbmcgui = types.ModuleType("xbmcgui")
xbmcgui.Dialog = lambda: MagicMock()
xbmcaddon = types.ModuleType("xbmcaddon")
xbmcaddon.Addon = _Addon

xbmcvfs = types.ModuleType("xbmcvfs")
xbmcvfs.translatePath = lambda path: path

sys.modules.setdefault("xbmc", xbmc)
sys.modules.setdefault("xbmcgui", xbmcgui)
sys.modules.setdefault("xbmcaddon", xbmcaddon)
sys.modules.setdefault("xbmcvfs", xbmcvfs)

from lib import search_history


def test_load_history_returns_empty_list_when_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(search_history, "ADDON_DATA", str(tmp_path))

    assert search_history.load_history() == []


def test_add_search_persists_term(tmp_path, monkeypatch):
    monkeypatch.setattr(search_history, "ADDON_DATA", str(tmp_path))

    search_history.add_search("matrix")

    with open(tmp_path / "search_history.json", "r", encoding="utf-8") as file:
        assert json.load(file) == ["matrix"]

    assert search_history.load_history() == ["matrix"]


def test_add_search_moves_duplicate_to_front(tmp_path, monkeypatch):
    monkeypatch.setattr(search_history, "ADDON_DATA", str(tmp_path))

    search_history.add_search("a")
    search_history.add_search("b")
    search_history.add_search("a")

    assert search_history.load_history() == ["a", "b"]


def test_add_search_caps_history_at_twenty_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(search_history, "ADDON_DATA", str(tmp_path))

    for idx in range(25):
        search_history.add_search("term-{}".format(idx))

    history = search_history.load_history()

    assert len(history) == 20
    assert history[0] == "term-24"
    assert history[-1] == "term-5"


def test_add_search_ignores_empty_terms(tmp_path, monkeypatch):
    monkeypatch.setattr(search_history, "ADDON_DATA", str(tmp_path))

    search_history.add_search("   ")

    assert search_history.load_history() == []


def test_clear_history_removes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(search_history, "ADDON_DATA", str(tmp_path))

    history_file = tmp_path / "search_history.json"
    with open(history_file, "w", encoding="utf-8") as file:
        json.dump(["matrix"], file)

    assert history_file.exists()

    search_history.clear_history()

    assert search_history.load_history() == []
    assert not history_file.exists()


def test_load_history_returns_empty_list_for_corrupt_json(tmp_path, monkeypatch):
    monkeypatch.setattr(search_history, "ADDON_DATA", str(tmp_path))

    history_file = tmp_path / "search_history.json"
    history_file.write_text("{not json}", encoding="utf-8")

    assert search_history.load_history() == []
