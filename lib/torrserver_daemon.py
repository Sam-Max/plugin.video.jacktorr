import hashlib
import logging
import os
import shutil

from lib.daemon import Daemon
from lib.os_platform import PLATFORM, System


def compute_hex_digest(file_path, hash_type, buff_size=4096):
    h = hash_type()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(buff_size), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_sha1(path):
    return compute_hex_digest(path, hashlib.sha1)


def get_current_app_id():
    with open("/proc/{:d}/cmdline".format(os.getpid())) as fp:
        return fp.read().rstrip("\0")


class TorrServerDaemonNotFoundError(Exception):
    pass


class ConfigError(LookupError):
    pass


class TorrServerDaemon(object):
    _sentinel = object()

    def __init__(
        self,
        name,
        directory,
        config=None,
        dest_dir=None,
        android_find_dest_dir=True,
        android_extra_dirs=(),
    ):
        self._name = name
        self._src_dir = directory
        self._src_path = os.path.join(self._src_dir, self._name)
        self._config = {} if config is None else config

        if not os.path.exists(self._src_path):
            raise TorrServerDaemonNotFoundError(
                "TorrServer daemon source path does not exist: " + self._src_path
            )

        if PLATFORM.system == System.android and android_find_dest_dir:
            app_dir = os.path.join(os.sep, "data", "data", get_current_app_id())
            if not os.path.exists(app_dir):
                logging.debug("Default android app dir '%s' does not exist", app_dir)
                for extra_dir in android_extra_dirs:
                    if os.path.exists(extra_dir):
                        app_dir = extra_dir
                        break

            logging.debug("Using android app dir '%s'", app_dir)
            self._dir = os.path.join(app_dir, "files", "torrserver")
        else:
            self._dir = directory if dest_dir is None else dest_dir

        self._path = os.path.join(self._dir, self._name)
        logging.debug("Using torrserver path '%s'", self._path)
        self._copy_to_dest()

    def setup(self):
        pass

    def start(self):
        raise NotImplementedError("Method start must be implemented")

    def stop(self):
        raise NotImplementedError("Method stop must be implemented")

    def poll(self):
        raise NotImplementedError("Method poll must be implemented")

    def get_config(self, config_name, default=_sentinel):
        config_value = self._config.get(config_name, default)
        if config_value is self._sentinel:
            raise ConfigError("No config named " + config_name)
        return config_value

    def set_config(self, config_name, config_value):
        self._config[config_name] = config_value

    def _copy_to_dest(self):
        if self._dir is not self._src_dir and (
            not os.path.exists(self._path)
            or compute_sha1(self._src_path) != compute_sha1(self._path)
        ):
            logging.info("Updating %s daemon '%s'", PLATFORM.system, self._path)
            if os.path.exists(self._dir):
                logging.debug("Removing old daemon dir %s", self._dir)
                shutil.rmtree(self._dir)
            shutil.copytree(self._src_dir, self._dir)


class TorrServerExecutableDaemon(TorrServerDaemon):
    def __init__(
        self,
        name,
        directory,
        config=None,
        dest_dir=None,
        android_find_dest_dir=True,
        android_extra_dirs=(),
        **kwargs
    ):
        super(TorrServerExecutableDaemon, self).__init__(
            name,
            directory,
            config=config,
            dest_dir=dest_dir,
            android_find_dest_dir=android_find_dest_dir,
            android_extra_dirs=android_extra_dirs,
        )
        self._daemon = Daemon(self._name, self._dir, **kwargs)

    def setup(self):
        self._daemon.ensure_exec_permissions()
        self._daemon.kill_leftover_process()

    def start(self):
        self._daemon.start(
            "--port",
            #str(self.get_config("port")),
            str(5665),
            logpath=self.get_config("log_path"),
        )

    def stop(self):
        self._daemon.stop()

    def poll(self):
        return self._daemon.daemon_poll()
