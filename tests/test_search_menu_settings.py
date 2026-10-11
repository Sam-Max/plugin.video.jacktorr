import sys
import types
from pathlib import Path
from unittest.mock import MagicMock
from xml.etree import ElementTree

import pytest


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

from lib import navigation, settings  # noqa: E402


ROOT = Path(__file__).parents[1]
SETTINGS_XML = ROOT / "resources" / "settings.xml"
LANGUAGE_DIR = ROOT / "resources" / "language"
LOCALES = ("en_gb", "es_es", "pt_br", "pt_pt", "ro_ro", "ru_ru")


def _po_entries(locale):
    entries = {}
    msgctxt = None
    for line in (LANGUAGE_DIR / ("resource.language." + locale) / "strings.po").read_text(
        encoding="utf-8"
    ).splitlines():
        line = line.strip()
        if line.startswith('msgctxt "#'):
            msgctxt = line[len('msgctxt "#') : -1]
            entries[msgctxt] = {"msgid": None, "msgstr": None}
        elif msgctxt is not None and line.startswith("msgid "):
            entries[msgctxt]["msgid"] = line[7:].strip('"')
        elif msgctxt is not None and line.startswith("msgstr "):
            entries[msgctxt]["msgstr"] = line[7:].strip('"')
            msgctxt = None
    return entries


def _index_listing(monkeypatch, show_rutor=False, show_torznab=False):
    monkeypatch.setattr(navigation, "api", MagicMock())
    monkeypatch.setattr(
        navigation, "translate", lambda string_id: "T{}".format(string_id)
    )
    monkeypatch.setattr(
        navigation, "li", lambda tid, icon: "item:T{}".format(tid)
    )
    add_directory_item = MagicMock()
    monkeypatch.setattr(navigation, "addDirectoryItem", add_directory_item)
    route_names = {
        id(navigation.search_results): "search_results",
        id(navigation.torznab_search_results): "torznab_search_results",
        id(navigation.dialog_insert): "dialog_insert",
        id(navigation.torrents): "torrents",
    }
    monkeypatch.setattr(
        navigation.plugin,
        "url_for",
        lambda func, **_kwargs: "plugin://" + route_names[id(func)],
    )
    monkeypatch.setattr(
        navigation,
        "show_rutor_search",
        lambda: show_rutor,
    )
    monkeypatch.setattr(
        navigation,
        "show_torznab_search",
        lambda: show_torznab,
    )
    return add_directory_item


def test_index_shows_no_search_entries_when_both_toggles_are_disabled(monkeypatch):
    add_directory_item = _index_listing(monkeypatch)

    navigation.index()

    destinations = [c.args[1] for c in add_directory_item.call_args_list]
    assert destinations == ["plugin://dialog_insert", "plugin://torrents"]


def test_index_shows_only_rutor_search_entry_when_only_rutor_is_enabled(monkeypatch):
    add_directory_item = _index_listing(monkeypatch, show_rutor=True)

    navigation.index()

    destinations = [c.args[1] for c in add_directory_item.call_args_list]
    labels = [c.args[2] for c in add_directory_item.call_args_list]
    assert destinations == [
        "plugin://search_results",
        "plugin://dialog_insert",
        "plugin://torrents",
    ]
    assert labels[0] == "item:T30255"


def test_index_shows_only_torznab_search_entry_when_only_torznab_is_enabled(monkeypatch):
    add_directory_item = _index_listing(monkeypatch, show_torznab=True)

    navigation.index()

    destinations = [c.args[1] for c in add_directory_item.call_args_list]
    labels = [c.args[2] for c in add_directory_item.call_args_list]
    assert destinations == [
        "plugin://torznab_search_results",
        "plugin://dialog_insert",
        "plugin://torrents",
    ]
    assert labels[0] == "item:T30261"


def test_index_shows_both_search_entries_when_both_toggles_are_enabled(monkeypatch):
    add_directory_item = _index_listing(monkeypatch, show_rutor=True, show_torznab=True)

    navigation.index()

    destinations = [c.args[1] for c in add_directory_item.call_args_list]
    labels = [c.args[2] for c in add_directory_item.call_args_list]
    assert destinations == [
        "plugin://search_results",
        "plugin://torznab_search_results",
        "plugin://dialog_insert",
        "plugin://torrents",
    ]
    assert labels == ["item:T30255", "item:T30261", "item:T30207", "item:T30206"]


def test_settings_xml_declares_local_search_toggles_disabled_by_default():
    root = ElementTree.parse(SETTINGS_XML).getroot()
    category = next(
        category
        for category in root.findall("category")
        if category.get("label") == "30087"
    )
    settings_by_id = {s.get("id"): s for s in category.findall("setting")}

    assert settings_by_id["show_rutor_search"].get("type") == "bool"
    assert settings_by_id["show_rutor_search"].get("default") == "false"
    assert settings_by_id["show_torznab_search"].get("type") == "bool"
    assert settings_by_id["show_torznab_search"].get("default") == "false"


def test_settings_xml_keeps_torrserver_rutor_setting_untouched():
    root = ElementTree.parse(SETTINGS_XML).getroot()
    category = next(
        category
        for category in root.findall("category")
        if category.get("label") == "30090"
    )
    server_settings = category.findall("setting")

    assert server_settings[-2].get("id") == "s:EnableRutorSearch"
    assert server_settings[-2].get("enable") == "eq(-24,true)"


def test_settings_xml_declares_torznab_server_toggle_after_rutor():
    root = ElementTree.parse(SETTINGS_XML).getroot()
    category = next(
        category
        for category in root.findall("category")
        if category.get("label") == "30090"
    )
    server_settings = category.findall("setting")
    torznab = server_settings[-1]

    assert torznab.get("id") == "s:EnableTorznabSearch"
    assert torznab.get("type") == "bool"
    assert torznab.get("default") == "false"
    assert torznab.get("visible") == "eq(-25,true)"
    assert torznab.get("enable") == "eq(-25,true)"


def test_local_search_toggle_getters_map_to_kodi_boolean_settings(monkeypatch):
    calls = []

    def fake_get_boolean_setting(setting):
        calls.append(setting)
        return True

    monkeypatch.setattr(settings, "get_boolean_setting", fake_get_boolean_setting)

    assert settings.show_rutor_search() is True
    assert settings.show_torznab_search() is True
    assert calls == ["show_rutor_search", "show_torznab_search"]


def test_rutor_search_label_is_renamed_in_every_locale():
    expected = {
        "en_gb": "Rutor search",
        "es_es": "Búsqueda Rutor",
        "pt_br": "Pesquisa Rutor",
        "pt_pt": "Pesquisa Rutor",
        "ro_ro": "Căutare Rutor",
        "ru_ru": "Поиск Rutor",
    }
    for locale in LOCALES:
        entry = _po_entries(locale)["30255"]
        assert entry["msgid"] == "Rutor search", locale
        assert entry["msgstr"] == expected[locale], locale


def test_show_search_setting_labels_exist_in_every_locale():
    for locale in LOCALES:
        entries = _po_entries(locale)
        assert entries["30268"]["msgid"] == "Show Rutor search", locale
        assert entries["30269"]["msgid"] == "Show Torznab search", locale
        assert entries["30268"]["msgstr"], locale
        assert entries["30269"]["msgstr"], locale


def test_server_search_toggle_labels_exist_in_every_locale():
    expected = {
        "en_gb": "Enable Torznab Search",
        "es_es": "Habilitar búsqueda Torznab",
        "pt_br": "Habilitar pesquisa Torznab",
        "pt_pt": "Habilitar pesquisa Torznab",
        "ro_ro": "Activează căutarea Torznab",
        "ru_ru": "Включить поиск Torznab",
    }
    for locale in LOCALES:
        entries = _po_entries(locale)
        assert entries["30270"]["msgid"] == "Enable Torznab Search", locale
        assert entries["30270"]["msgstr"] == expected[locale], locale
        assert entries["30271"]["msgid"] == "No results", locale
        assert entries["30271"]["msgstr"], locale
