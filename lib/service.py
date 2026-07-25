import json
import logging
import os
import threading
from requests import request
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException
from lib.utils import assure_unicode, megabytes_to_bytes
import xbmc
import xbmcgui

from lib import kodi
from lib.settings import (
    get_password,
    get_port,
    get_service_host,
    get_username,
    apply_settings_to_torrserver,
    service_enabled,
    ssl_enabled,
)


class AbortRequestedError(Exception):
    pass


class DaemonTimeoutError(Exception):
    pass


class DaemonMonitor(xbmc.Monitor):
    _settings_prefix = "s"
    _settings_separator = ":"
    _settings_get_uri = "settings"
    _settings_set_uri = "settings"

    settings_name = "settings.json"
    log_name = "torrserver.log"

    def __init__(self):
        super(DaemonMonitor, self).__init__()
        self._lock = threading.Lock()
        self._settings_path = os.path.join(kodi.ADDON_DATA, self.settings_name)
        self._log_path = os.path.join(kodi.ADDON_DATA, self.log_name)
        self._enabled = None
        self._host = get_service_host()
        self._port = get_port()
        self._username = get_username()
        self._password = get_password()
        self._auth = HTTPBasicAuth(self._username, self._password)
        self._ssl_enabled = ssl_enabled()
        self._base_url = "{}://{}:{}".format(
            "https" if self._ssl_enabled else "http", self._host, self._port
        )
        self._settings_spec = [
            s
            for s in kodi.get_all_settings_spec()
            if s["id"].startswith(self._settings_prefix + self._settings_separator)
        ]

    def _request(self, method, url, **kwargs):
        return request(
            method,
            f"{self._base_url}/{url}",
            auth=self._auth,
            **kwargs,
        )

    def _get_kodi_settings(self):
        s = kodi.generate_dict_settings(
            self._settings_spec, separator=self._settings_separator
        )[self._settings_prefix]
        s["TorrentsSavePath"] = assure_unicode(
            kodi.translatePath(s["TorrentsSavePath"])
        )
        s["CacheSize"] = megabytes_to_bytes(s["CacheSize"])
        return s

    def _get_daemon_settings(self):
        try:
            r = self._request(
                "post", self._settings_get_uri, data=json.dumps({"action": "get"})
            )
        except RequestException as error:
            logging.error(
                "TorrServer is unavailable at %s; settings will sync on the next change: %s",
                self._base_url,
                error,
            )
            return None
        if r.status_code != 200:
            logging.error(
                "Failed getting daemon settings with code %d: %s", r.status_code, r.text
            )
            return None
        return r.json()

    def _update_kodi_settings(self):
        daemon_settings = self._get_daemon_settings()
        if daemon_settings is None:
            return False
        kodi.set_settings_dict(
            daemon_settings,
            prefix=self._settings_prefix,
            separator=self._settings_separator,
        )
        return True

    def _refresh_connection(self):
        """Re-read connection settings so the long-running monitor picks up
        host/port/credential changes without requiring a Kodi restart."""
        self._host = get_service_host()
        self._port = get_port()
        self._username = get_username()
        self._password = get_password()
        self._auth = HTTPBasicAuth(self._username, self._password)
        self._ssl_enabled = ssl_enabled()
        self._base_url = "{}://{}:{}".format(
            "https" if self._ssl_enabled else "http", self._host, self._port
        )

    def _update_daemon_settings(self):
        self._refresh_connection()
        if not apply_settings_to_torrserver():
            return True

        daemon_settings = self._get_daemon_settings()
        if daemon_settings is None:
            return False

        kodi_settings = self._get_kodi_settings()
        if daemon_settings != kodi_settings:
            r = self._request(
                "post",
                self._settings_set_uri,
                data=json.dumps({"action": "set", "sets": kodi_settings}),
            )
            if r.status_code != 200:
                xbmcgui.Dialog().ok(kodi.translate(30102), r.json()["error"])
                return False

        return True

    def onSettingsChanged(self):
        with self._lock:
            enabled = service_enabled()
            if enabled != self._enabled:
                self._enabled = enabled

            if self._enabled:
                self._update_daemon_settings()

    def start(self):
        try:
            self.onSettingsChanged()
        except DaemonTimeoutError:
            logging.error("Timed out waiting for daemon")
        # Keep the monitor alive so Kodi can deliver onSettingsChanged callbacks
        # after runtime setting toggles. Without this loop the service thread ends
        # immediately after the initial sync and no later setting change reaches
        # the daemon.
        self.waitForAbort()


@kodi.once("migrated")
def handle_first_run():
    logging.info("Handling first run")
    xbmcgui.Dialog().ok(kodi.translate(30100), kodi.translate(30101))
    kodi.open_settings()


def run():
    kodi.set_logger()
    handle_first_run()
    DaemonMonitor().start()
