import json
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

from lib import service


def _monitor():
    monitor = service.DaemonMonitor.__new__(service.DaemonMonitor)
    monitor._settings_set_uri = "settings"
    return monitor


def test_update_daemon_settings_skips_remote_write_when_sync_disabled(monkeypatch):
    monitor = _monitor()
    monitor._get_daemon_settings = MagicMock()

    monkeypatch.setattr(service, "apply_settings_to_torrserver", lambda: False)

    assert monitor._update_daemon_settings() is True
    monitor._get_daemon_settings.assert_not_called()


def test_update_daemon_settings_writes_when_sync_enabled_and_settings_differ(monkeypatch):
    monitor = _monitor()
    monitor._get_daemon_settings = MagicMock(return_value={"CacheSize": 1})
    monitor._get_kodi_settings = MagicMock(return_value={"CacheSize": 2})
    monitor._request = MagicMock(return_value=MagicMock(status_code=200))

    monkeypatch.setattr(service, "apply_settings_to_torrserver", lambda: True)

    assert monitor._update_daemon_settings() is True
    monitor._request.assert_called_once_with(
        "post",
        "settings",
        data=json.dumps({"action": "set", "sets": {"CacheSize": 2}}),
    )


def test_update_daemon_settings_does_not_write_when_enabled_settings_match(monkeypatch):
    monitor = _monitor()
    settings = {"CacheSize": 2}
    monitor._get_daemon_settings = MagicMock(return_value=settings)
    monitor._get_kodi_settings = MagicMock(return_value=settings)
    monitor._request = MagicMock()

    monkeypatch.setattr(service, "apply_settings_to_torrserver", lambda: True)

    assert monitor._update_daemon_settings() is True
    monitor._request.assert_not_called()
