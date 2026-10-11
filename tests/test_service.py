import json
import logging
import sys
import threading
import types
from unittest.mock import MagicMock

import pytest
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

    def getSetting(self, setting):
        return {"service_host": "localhost", "service_port": "8090"}.get(
            setting, "0"
        )

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


def _sync_monitor(daemon_settings, kodi_settings):
    monitor = _monitor()
    monitor._refresh_connection = MagicMock()
    monitor._get_daemon_settings = MagicMock(return_value=daemon_settings)
    monitor._get_kodi_settings = MagicMock(return_value=kodi_settings)
    monitor._request = MagicMock(return_value=MagicMock(status_code=200))
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


def test_update_daemon_settings_preserves_unmanaged_server_fields(monkeypatch):
    daemon_settings = {
        "EnableRutorSearch": False,
        "EnableTorznabSearch": False,
        "TorznabUrls": [{"Name": "indexer", "Url": "http://secret"}],
        "Indexers": {"token": "abc"},
        "Nested": {"A": 1, "B": {"C": True}},
        "KeepFalse": False,
        "KeepZero": 0,
        "KeepEmpty": "",
    }
    kodi_settings = {"EnableRutorSearch": True, "EnableTorznabSearch": True}
    monitor = _sync_monitor(daemon_settings, kodi_settings)
    monkeypatch.setattr(service, "apply_settings_to_torrserver", lambda: True)

    assert monitor._update_daemon_settings() is True

    monitor._request.assert_called_once()
    payload = json.loads(monitor._request.call_args.kwargs["data"])
    assert payload["action"] == "set"
    assert payload["sets"]["EnableRutorSearch"] is True
    assert payload["sets"]["EnableTorznabSearch"] is True
    assert payload["sets"]["TorznabUrls"] == [
        {"Name": "indexer", "Url": "http://secret"}
    ]
    assert payload["sets"]["Indexers"] == {"token": "abc"}
    assert payload["sets"]["Nested"] == {"A": 1, "B": {"C": True}}
    assert payload["sets"]["KeepFalse"] is False
    assert payload["sets"]["KeepZero"] == 0
    assert payload["sets"]["KeepEmpty"] == ""


def test_update_daemon_settings_skips_write_when_only_remote_fields_differ(monkeypatch):
    kodi_settings = {"EnableRutorSearch": True}
    daemon_settings = {
        "EnableRutorSearch": True,
        "EnableTorznabSearch": False,
        "TorznabUrls": ["http://indexer"],
    }
    monitor = _sync_monitor(daemon_settings, kodi_settings)
    monkeypatch.setattr(service, "apply_settings_to_torrserver", lambda: True)

    assert monitor._update_daemon_settings() is True
    monitor._request.assert_not_called()


def test_get_daemon_settings_rejects_invalid_json_and_non_object_payloads(caplog):
    monitor = _monitor()
    monitor._base_url = "http://127.0.0.1:5665"
    responses = [
        MagicMock(status_code=200, json=MagicMock(side_effect=ValueError("bad json"))),
        MagicMock(status_code=200, json=MagicMock(return_value=["not", "a", "dict"])),
        MagicMock(status_code=200, json=MagicMock(return_value="secret-token")),
    ]
    for response in responses:
        monitor._request = MagicMock(return_value=response)
        with caplog.at_level(logging.ERROR):
            assert monitor._get_daemon_settings() is None

    assert "invalid JSON" in caplog.text or "payload" in caplog.text
    assert "secret-token" not in caplog.text


def test_update_daemon_settings_never_posts_invalid_remote_config(monkeypatch, caplog):
    monitor = _monitor()
    monitor._refresh_connection = MagicMock()
    monitor._request = MagicMock(
        return_value=MagicMock(
            status_code=200,
            json=MagicMock(side_effect=ValueError("invalid json")),
        )
    )
    monkeypatch.setattr(service, "apply_settings_to_torrserver", lambda: True)

    with caplog.at_level(logging.ERROR):
        assert monitor._update_daemon_settings() is False

    assert monitor._request.call_count == 1
    payload = json.loads(monitor._request.call_args.kwargs["data"])
    assert payload["action"] == "get"


def test_settings_spec_never_exports_local_search_toggles_to_server():
    ids = [s["id"] for s in service.kodi.get_all_settings_spec()]

    assert "show_rutor_search" in ids
    assert "show_torznab_search" in ids
    assert "s:show_rutor_search" not in ids
    assert "s:show_torznab_search" not in ids
    assert "s:EnableTorznabSearch" in ids


class _FakeHTTPResult:
    def __init__(self, status_code, payload=None, raw=None):
        self.status_code = status_code
        self._payload = payload
        self._raw = raw
        self.text = raw if raw is not None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError(self._raw)
        return self._payload


class _FakeTorrServer:
    """In-memory HTTP transport modelling TorrServer's full-replacement
    settings API: GET-style post(action=get) returns the stored dict,
    post(action=set) replaces it entirely. Records every request."""

    def __init__(self, initial=None):
        self.config = dict(initial or {})
        self.requests = []

    def __call__(self, method, url, **kwargs):
        self.requests.append((method, url, json.loads(kwargs["data"])))
        action = json.loads(kwargs["data"])["action"]
        if action == "get":
            return _FakeHTTPResult(200, payload=dict(self.config))
        self.config = json.loads(kwargs["data"])["sets"]
        return _FakeHTTPResult(200, payload={})


def _public_monitor(monkeypatch, server, addon_settings=None):
    """Build a DaemonMonitor driven only through the public onSettingsChanged
    callback with a mocked HTTP transport and stubbed local addon settings."""
    monitor = _monitor()
    monitor._lock = threading.Lock()
    monitor._enabled = None
    monitor._request = server
    # Derive the s:* export spec from the real settings.xml, as __init__ does.
    monitor._settings_spec = [
        s
        for s in service.kodi.get_all_settings_spec()
        if s["id"].startswith("s:")
    ]
    addon_settings = dict(addon_settings or {})
    # Seed every s:* setting with its real settings.xml default so the spec
    # export reads like a real Kodi settings store.
    for spec in monitor._settings_spec:
        addon_settings.setdefault(spec["id"], spec.get("default", ""))
    addon_settings.setdefault("service_host", "localhost")
    addon_settings.setdefault("service_port", "8090")
    addon_settings.setdefault("service_login", "")
    addon_settings.setdefault("service_password", "")

    def fake_get_setting(setting):
        return addon_settings.get(setting, "")

    def fake_translatePath(path):
        return path

    # lib.kodi binds get_setting = ADDON.getSetting at import time, so patch
    # the module-level alias (the real read path used by the s:* spec export).
    monkeypatch.setattr(service.kodi, "get_setting", fake_get_setting)
    monkeypatch.setattr(service.kodi, "translatePath", fake_translatePath)
    monkeypatch.setattr(service, "service_enabled", lambda: True)
    monkeypatch.setattr(service, "apply_settings_to_torrserver", lambda: True)
    return monitor


def _assert_preserved_unmanaged_fields(payload):
    assert payload["TorznabUrls"] == [
        {"Name": "dummy", "Url": "http://indexer.invalid", "Host": "h",
         "Key": "DUMMY-INDEXER-KEY"}
    ]
    assert payload["Indexers"] == {"token": "DUMMY-INDEXER-KEY"}
    assert payload["Nested"] == {"A": 1, "B": {"C": True}}
    assert payload["KeepFalse"] is False
    assert payload["KeepZero"] == 0
    assert payload["KeepEmpty"] == ""
    assert "UnknownFutureField" in payload


_REMOTE_CONFIG = {
    "EnableRutorSearch": False,
    "EnableTorznabSearch": False,
    "TorznabUrls": [
        {"Name": "dummy", "Url": "http://indexer.invalid", "Host": "h",
         "Key": "DUMMY-INDEXER-KEY"}
    ],
    "Indexers": {"token": "DUMMY-INDEXER-KEY"},
    "Nested": {"A": 1, "B": {"C": True}},
    "KeepFalse": False,
    "KeepZero": 0,
    "KeepEmpty": "",
    "UnknownFutureField": "keep",
}


def _managed_export_defaults():
    """Compute the managed s:* export values the same way the addon does,
    from the real settings.xml spec defaults (independent of production code)."""
    export = {}
    for spec in service.kodi.get_all_settings_spec():
        if not spec["id"].startswith("s:"):
            continue
        key = spec["id"].split(":", 1)[1]
        default = spec.get("default", "")
        kind = spec["type"]
        if kind in ("number", "enum") or (
            kind == "slider" and spec.get("option") == "int"
        ):
            export[key] = int(default) if default else 0
        elif kind == "bool":
            export[key] = default.lower() == "true"
        else:
            export[key] = default
    export["CacheSize"] = service.megabytes_to_bytes(export["CacheSize"])
    return export


def test_public_on_settings_changed_overlays_managed_settings_only(monkeypatch):
    server = _FakeTorrServer(initial=_REMOTE_CONFIG)
    monitor = _public_monitor(
        monkeypatch,
        server,
        addon_settings={"s:EnableRutorSearch": "true", "s:CacheSize": "25"},
    )

    monitor.onSettingsChanged()

    sets = [r[2]["sets"] for r in server.requests if r[2].get("action") == "set"]
    assert len(sets) == 1
    payload = sets[0]
    assert payload["EnableRutorSearch"] is True
    assert payload["CacheSize"] == 25 * 1024 * 1024
    assert payload["TorrentsSavePath"] == "/opt/ts/torrents"
    _assert_preserved_unmanaged_fields(payload)


def test_public_on_settings_changed_skips_write_when_overlay_is_noop(monkeypatch):
    remote = dict(_REMOTE_CONFIG)
    # Every managed s:* field must already match the addon's exported values.
    remote.update(_managed_export_defaults())
    remote["EnableRutorSearch"] = True
    server = _FakeTorrServer(initial=remote)
    monitor = _public_monitor(
        monkeypatch,
        server,
        addon_settings={"s:EnableRutorSearch": "true", "s:CacheSize": "25"},
    )

    monitor.onSettingsChanged()

    assert not [r for r in server.requests if r[2].get("action") == "set"]


def test_public_on_settings_changed_repeated_calls_issue_single_write(monkeypatch):
    server = _FakeTorrServer(initial=_REMOTE_CONFIG)
    monitor = _public_monitor(
        monkeypatch,
        server,
        addon_settings={"s:EnableRutorSearch": "true"},
    )

    monitor.onSettingsChanged()
    monitor.onSettingsChanged()

    sets = [r for r in server.requests if r[2].get("action") == "set"]
    assert len(sets) == 1


def test_public_callback_makes_no_requests_when_sync_gate_is_off(monkeypatch):
    server = _FakeTorrServer(initial=_REMOTE_CONFIG)
    monitor = _public_monitor(monkeypatch, server)
    monkeypatch.setattr(service, "apply_settings_to_torrserver", lambda: False)

    monitor.onSettingsChanged()

    assert server.requests == []


def test_public_callback_makes_no_requests_when_service_is_disabled(monkeypatch):
    server = _FakeTorrServer(initial=_REMOTE_CONFIG)
    monitor = _public_monitor(monkeypatch, server)
    monkeypatch.setattr(service, "service_enabled", lambda: False)

    monitor.onSettingsChanged()

    assert server.requests == []


@pytest.mark.parametrize("payload", [None, ["not", "a", "dict"], "secret-token"])
def test_public_callback_never_writes_rejected_remote_config(monkeypatch, payload):
    server = _FakeTorrServer(initial=_REMOTE_CONFIG)
    monitor = _public_monitor(
        monkeypatch,
        server,
        addon_settings={"s:EnableRutorSearch": "true"},
    )
    if payload is None:
        server_result = _FakeHTTPResult(200, raw="not-json {{")
        response = server_result
    else:
        response = _FakeHTTPResult(200, payload=payload)

    def broken_get(method, url, **kwargs):
        if json.loads(kwargs["data"]).get("action") == "get":
            return response
        return server(method, url, **kwargs)

    monitor._request = broken_get

    assert monitor.onSettingsChanged() is None

    assert not [r for r in server.requests if r[2].get("action") == "set"]
    assert server.config == _REMOTE_CONFIG
    ids = [s["id"] for s in service.kodi.get_all_settings_spec()]

    assert "show_rutor_search" in ids
    assert "show_torznab_search" in ids
    assert "s:show_rutor_search" not in ids
    assert "s:show_torznab_search" not in ids
    assert "s:EnableTorznabSearch" in ids


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
