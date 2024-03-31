import json
import requests


class TorrServer(object):
    def __init__(self, host, port, session=None):
        self._base_url = "http://{}:{}".format(host, port)
        self._session = session or requests

    @property
    def torr_version(self):
        """tests server status"""
        return self._get("/echo").content

    def add_magnet(self, magnet, title, poster="", data2=""):
        return self._post(
            "/torrents",
            data=json.dumps(
                {
                    "action": "add",
                    "link": magnet,
                    "title": title,
                    "poster": poster,
                    "data": data2,
                    "save_to_db": True,
                }
            ),
        )

    def add_torrent(self, path, title, poster, data):
        with open(path, "rb") as file:
            return self._post(
                "/torrent/upload",
                files={"file": file},
                data=json.dumps(
                    {
                        "save": "true",
                        "title": title,
                        "poster": poster,
                        "data": data,
                    }
                ),
            )

    def torrents(self):
        """read info about all torrents (doesn't fill file_stats info)"""
        return self._post("/torrents", data=json.dumps({"action": "list"})).json()

    def get_torrent_info_not_extended(self, hash):
        """not extended"""
        return self._post(
            "/torrents", data=json.dumps({"action": "get", "hash": hash})
        ).json()

    def get_torrent_info(self, link):
        """read extended info of one torrent"""
        return self._get("/stream", params={"link": link, "stat": "true"}).json()

    def torrent_drop(self, hash):
        return self._post(
            "/torrents", data=json.dumps({"action": "drop", "hash": hash})
        ).json()

    def remove_torrent(self, info_hash, save_to_db=True):
        """delete torrent from TorrServer"""
        return self._post(
            "/torrents",
            data=json.dumps(
                {"action": "rem", "hash": info_hash, "save_to_db": save_to_db}
            ),
        )

    def play_torrent(self, hash, id):
        """Play given torrent referenced by hash"""
        return self._get("/play", params={"hash": hash, "id": id})

    def play_stream(self, link, title="", poster=""):
        return self._get(
            "/stream",
            params={"link": link, "title": title, "poster": poster, "play": "true"},
        )

    def serve_url(self, path, link, file_id=1):
        return f"{self._base_url}/stream/{path}?link={link}&index={file_id}&play"

    def get_stream_url(self, link, path, file_id, title=""):
        """preload torrent, returns the stream url"""
        res = self._get(
            "/stream",
            params={"link": link, "title": title, "stat": "true", "preload": "true"},
        )
        if res:
            return self.serve_url(path, link, file_id)

    def get_settings(self):
        res = self._post("/settings", data=json.dumps({"action": "get"}))
        for k, v in res.json().items():
            print(f"{k}:{v}")

    def _post(self, url, **kwargs):
        return self._request("post", url, **kwargs)

    def _put(self, url, **kwargs):
        return self._request("put", url, **kwargs)

    def _get(self, url, **kwargs):
        return self._request("get", url, **kwargs)

    def _delete(self, url, **kwargs):
        return self._request("delete", url, **kwargs)

    def _request(self, method, url, validate=True, **kwargs):
        res = self._session.request(method, self._base_url + url, **kwargs)
        if validate and res.status_code >= 400:
            raise TorrServerError(res.text)
        return res

class TorrServerError(Exception):
    pass