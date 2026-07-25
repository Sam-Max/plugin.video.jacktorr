import json
import logging
import sys
import threading
import types
from unittest.mock import MagicMock

from requests.exceptions import ConnectionError


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
    monitor._refresh_connection = MagicMock()
    monitor._get_daemon_settings = MagicMock()

    monkeypatch.setattr(service, "apply_settings_to_torrserver", lambda: False)

    assert monitor._update_daemon_settings() is True
    monitor._refresh_connection.assert_called_once_with()
    monitor._get_daemon_settings.assert_not_called()


def test_get_daemon_settings_handles_unavailable_torrserver(caplog):
    monitor = _monitor()
    monitor._base_url = "http://192.168.50.26:5665"
    monitor._request = MagicMock(side_effect=ConnectionError("Connection refused"))

    with caplog.at_level(logging.ERROR):
        assert monitor._get_daemon_settings() is None

    assert "TorrServer is unavailable at http://192.168.50.26:5665" in caplog.text


def test_settings_callback_retries_after_unavailable_daemon(monkeypatch):
    monitor = _monitor()
    monitor._lock = threading.Lock()
    monitor._enabled = None
    monitor._update_daemon_settings = MagicMock(return_value=False)
    monkeypatch.setattr(service, "service_enabled", lambda: True)

    monitor.onSettingsChanged()
    monitor.onSettingsChanged()

    assert monitor._update_daemon_settings.call_count == 2


def test_update_daemon_settings_writes_when_sync_enabled_and_settings_differ(monkeypatch):
    monitor = _monitor()
    monitor._refresh_connection = MagicMock()
    monitor._get_daemon_settings = MagicMock(return_value={"CacheSize": 1})
    monitor._get_kodi_settings = MagicMock(return_value={"CacheSize": 2})
    monitor._request = MagicMock(return_value=MagicMock(status_code=200))

    monkeypatch.setattr(service, "apply_settings_to_torrserver", lambda: True)

    assert monitor._update_daemon_settings() is True
    monitor._refresh_connection.assert_called_once_with()
    monitor._request.assert_called_once_with(
        "post",
        "settings",
        data=json.dumps({"action": "set", "sets": {"CacheSize": 2}}),
    )


def test_update_daemon_settings_does_not_write_when_enabled_settings_match(monkeypatch):
    monitor = _monitor()
    monitor._refresh_connection = MagicMock()
    settings = {"CacheSize": 2}
    monitor._get_daemon_settings = MagicMock(return_value=settings)
    monitor._get_kodi_settings = MagicMock(return_value=settings)
    monitor._request = MagicMock()

    monkeypatch.setattr(service, "apply_settings_to_torrserver", lambda: True)

    assert monitor._update_daemon_settings() is True
    monitor._refresh_connection.assert_called_once_with()
    monitor._request.assert_not_called()


def test_start_syncs_then_waits_for_abort():
    monitor = _monitor()
    monitor.onSettingsChanged = MagicMock()
    monitor.waitForAbort = MagicMock()

    monitor.start()

    monitor.onSettingsChanged.assert_called_once_with()
    monitor.waitForAbort.assert_called_once_with()


def test_refresh_connection_reloads_settings(monkeypatch):
    monitor = _monitor()

    monkeypatch.setattr(service, "get_service_host", lambda: "new-host")
    monkeypatch.setattr(service, "get_port", lambda: "9000")
    monkeypatch.setattr(service, "get_username", lambda: "new-user")
    monkeypatch.setattr(service, "get_password", lambda: "new-password")
    monkeypatch.setattr(service, "ssl_enabled", lambda: True)

    monitor._refresh_connection()

    assert monitor._host == "new-host"
    assert monitor._port == "9000"
    assert monitor._username == "new-user"
    assert monitor._password == "new-password"
    assert monitor._base_url == "https://new-host:9000"
    assert monitor._auth.username == "new-user"
    assert monitor._auth.password == "new-password"


def test_update_daemon_settings_refreshes_connection_before_gate(monkeypatch):
    monitor = _monitor()
    calls = []
    monitor._refresh_connection = MagicMock(side_effect=lambda: calls.append("refresh"))
    monitor._get_daemon_settings = MagicMock()

    def sync_gate():
        calls.append("gate")
        return False

    monkeypatch.setattr(service, "apply_settings_to_torrserver", sync_gate)

    assert monitor._update_daemon_settings() is True
    assert calls == ["refresh", "gate"]
    monitor._get_daemon_settings.assert_not_called()
