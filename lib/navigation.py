import logging
import os
from threading import Thread
import time

import requests
from lib.torrserver.api import TorrServer
import routing
from xbmc import Monitor, executebuiltin, getInfoLabel, getCondVisibility, sleep
from xbmcgui import ListItem, DialogProgress, Dialog
from xbmcplugin import addDirectoryItem, endOfDirectory, setResolvedUrl

from lib.dialog import DialogInsert
from lib.kodi import (
    ADDON_PATH,
    ADDON_NAME,
    translate,
    notification,
    set_logger,
    refresh,
    show_picture,
    close_busy_dialog,
)
from lib.kodi_formats import is_music, is_picture, is_video, is_text
from lib.player import JackTorrPlayer
from lib.settings import (
    get_password,
    get_service_host,
    get_port,
    get_buffering_timeout,
    get_username,
    show_status_overlay,
    get_min_candidate_size,
    ask_to_delete_torrent,
    get_files_order,
    get_metadata_timeout,
    ssl_enabled,
)
from lib.utils import sizeof_fmt

set_logger()
plugin = routing.Plugin()


api = TorrServer(
    get_service_host(), get_port(), get_username(), get_password(), ssl_enabled()
)


class PlayError(Exception):
    def handle(self):
        pass


class CanceledError(PlayError):
    def __init__(self, e, info_hash, name):
        super(CanceledError, self).__init__(e)
        self._info_hash = info_hash
        self._name = name

    def handle(self):
        handle_player_stop(self._info_hash, self._name)


def check_playable(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            if not getattr(e, "%_checked", False):
                setResolvedUrl(plugin.handle, False, ListItem())
                if isinstance(e, PlayError):
                    logging.debug(e)
                    e.handle()
                    return
                setattr(e, "%_checked", True)
            raise e

    return wrapper


def check_directory(func):
    def wrapper(*args, **kwargs):
        succeeded = False
        try:
            ret = func(*args, **kwargs)
            succeeded = True
            return ret
        finally:
            endOfDirectory(plugin.handle, succeeded=succeeded)

    return wrapper


def li(tid, icon):
    return list_item(translate(tid), icon)


def list_item(label, icon):
    item = ListItem(label)
    item.setArt({"icon": os.path.join(ADDON_PATH, "resources", "images", icon)})
    return item


def action(func, *args, **kwargs):
    return "RunPlugin({})".format(plugin.url_for(func, *args, **kwargs))


def media(func, *args, **kwargs):
    return "PlayMedia({})".format(plugin.url_for(func, *args, **kwargs))


def query_arg(name, required=True):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if name not in kwargs:
                query_list = plugin.args.get(name)
                if query_list:
                    kwargs[name] = query_list[0]
                elif required:
                    raise AttributeError(
                        "Missing {} required query argument".format(name)
                    )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def get_state_string(state):
    if state == 0:
        return "Torrent added"
    elif state == 1:
        return "Torrent getting info"
    elif state == 2:
        return "Torrent preload"
    elif state == 3:
        return "Torrent working"
    elif state == 4:
        return "Torrent closed"
    elif state == 5:
        return "Torrent in db"
    else:
        return translate(30230)


def get_status_labels(info_hash):
    info = api.get_torrent_info(info_hash)
    return (
        "{:s}".format(get_state_string(info.get("stat"))),
        "D:{:s}/s U:{:s}/s S:{:d} P:{:d}/{:d}".format(
            sizeof_fmt(info.get("download_speed")),
            sizeof_fmt(info.get("upload_speed")),
            info.get("connected_seeders"),
            info.get("active_peers"),
            info.get("total_peers"),
        ),
    )


def handle_player_stop(info_hash, name, initial_delay=0.5, listing_timeout=10):
    if not ask_to_delete_torrent():
        return

    sleep(int(initial_delay * 1000))
    start_time = time.time()
    while (
        getCondVisibility("Window.IsActive(busydialog)")
        and not 0 < listing_timeout < time.time() - start_time
    ):
        sleep(100)

    remove_torrent = Dialog().yesno(ADDON_NAME, name + "\n" + translate(30241))
    if remove_torrent:
        api.remove_torrent(info_hash)
        current_folder = getInfoLabel("Container.FolderPath")
        if current_folder == plugin.url_for(torrent_files, info_hash):
            executebuiltin("Action(Back)")
        elif current_folder == plugin.url_for(torrents):
            refresh()


@plugin.route("/")
@check_directory
def index():
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(torrents),
        li(30206, "torrents.png"),
        isFolder=True,
    )
    addDirectoryItem(
        plugin.handle,
        plugin.url_for(dialog_insert),
        li(30207, "add.png"),
        isFolder=False,
    )


@plugin.route("/torrents")
@check_directory
def torrents():
    for torrent in api.torrents():
        info_hash = torrent.get("hash")

        context_menu_items = [
            (translate(30235), media(play_info_hash, info_hash=info_hash))
        ]

        if torrent.get("stat") in [2, 3]:
            context_menu_items.append(
                (translate(30208), action(torrent_action, info_hash, "drop"))
            )

        context_menu_items.extend(
            [
                (
                    translate(30242),
                    action(torrent_action, info_hash, "remove_torrent"),
                ),
                (
                    translate(30245),
                    action(torrent_action, info_hash, "torrent_status"),
                ),
            ]
        )

        torrent_li = list_item(torrent.get("title", ""), "download.png")
        torrent_li.addContextMenuItems(context_menu_items)
        addDirectoryItem(
            plugin.handle,
            plugin.url_for(torrent_files, info_hash),
            torrent_li,
            isFolder=True,
        )


@plugin.route("/torrents/<info_hash>/<action_str>")
def torrent_action(info_hash, action_str):
    needs_refresh = True

    if action_str == "drop":
        api.drop_torrent(info_hash)
    elif action_str == "remove_torrent":
        api.remove_torrent(info_hash)
    elif action_str == "torrent_status":
        torrent_status(info_hash)
        needs_refresh = False
    else:
        logging.error("Unknown action '%s'", action_str)
        needs_refresh = False

    if needs_refresh:
        refresh()


@plugin.route("/torrents/<info_hash>/files/<file_id>/<action_str>")
def file_action(info_hash, file_id, action_str):
    if action_str == "download":
        api.download_file(info_hash, file_id)
    elif action_str == "drop":
        api.drop_torrent(info_hash, file_id)
    else:
        logging.error("Unknown action '%s'", action_str)
        return
    refresh()


def torrent_status(info_hash):
    status = api.get_torrent_info(link=info_hash)
    notification(
        "{}".format(status.get("stat_string")),
        status.get("name"),
        sound=False,
    )


def sort_files(files):
    order = get_files_order()
    if order == 1:
        files.sort(key=lambda k: k.name)
    elif order == 2:
        files.sort(key=lambda k: k.length)


@plugin.route("/torrents/<info_hash>")
@check_directory
def torrent_files(info_hash):
    info = api.get_torrent_info(link=info_hash)
    file_stats = info.get("file_stats")

    for f in file_stats:
        name = f.get("path")
        id = f.get("id")
        serve_url = api.get_stream_url(link=info_hash, path=f.get("path"), file_id=id)
        file_li = list_item(name, "download.png")
        file_li.setPath(serve_url)

        context_menu_items = []
        info_labels = {"title": info.get("title")}
        kwargs = dict(info_hash=info_hash, file_id=id, path=name)

        if is_picture(name):
            url = plugin.url_for(display_picture, **kwargs)
            file_li.setInfo("pictures", info_labels)
        elif is_text(name):
            url = plugin.url_for(display_text, **kwargs)
        else:
            url = serve_url
            if is_video(name):
                info_type = "video"
            elif is_music(name):
                info_type = "music"
            else:
                info_type = None

            if info_type is not None:
                url = plugin.url_for(play, **kwargs)
                file_li.setInfo(info_type, info_labels)
                file_li.setProperty("IsPlayable", "true")

                context_menu_items.append(
                    (translate(30235), media(buffer_and_play, **kwargs))
                )

        file_li.addContextMenuItems(context_menu_items)

        addDirectoryItem(plugin.handle, url, file_li)


@plugin.route("/display_picture/<info_hash>/<file_id>")
@query_arg("path")
def display_picture(info_hash, file_id, path):
    show_picture(api.get_stream_url(link=info_hash, path=path, file_id=file_id))


@plugin.route("/display_text/<info_hash>/<file_id>")
@query_arg("path")
def display_text(info_hash, file_id, path):
    r = requests.get(api.get_stream_url(link=info_hash, path=path, file_id=file_id))
    Dialog().textviewer(path, r.text)


@plugin.route("/play_url")
@query_arg("url")
@check_playable
def play_url(url, buffer=True):
    r = requests.get(url, stream=True)
    info_hash = api.add_torrent_obj(r.raw)
    play_info_hash(info_hash=info_hash, buffer=buffer)


@plugin.route("/play_magnet")
@query_arg("magnet")
@check_playable
def play_magnet(magnet, buffer=True):
    info_hash = api.add_magnet(magnet)
    play_info_hash(info_hash=info_hash, buffer=buffer)


@plugin.route("/play_path")
@query_arg("path")
@check_playable
def play_file(path, buffer=True):
    info_hash = api.add_torrent(path)
    play_info_hash(info_hash=info_hash, buffer=buffer)


@plugin.route("/play_info_hash")
@query_arg("info_hash")
@check_playable
def play_info_hash(info_hash, buffer=True):
    info = api.get_torrent_info(info_hash)
    if info.get("stat") == 1:
        wait_for_metadata(info_hash)

    files = info.get("file_stats")
    min_candidate_size = get_min_candidate_size() * 1024 * 1024
    candidate_files = [
        f
        for f in files
        if is_video(f.get("path")) and f.get("length") >= min_candidate_size
    ]
    if not candidate_files:
        notification(translate(30239))
        raise PlayError("No candidate files found for {}".format(info_hash))
    elif len(candidate_files) == 1:
        chosen_file = candidate_files[0]
    else:
        sort_files(candidate_files)
        chosen_index = Dialog().select(
            translate(30240), [f.get("path") for f in candidate_files]
        )
        if chosen_index < 0:
            raise PlayError("User canceled dialog select")
        chosen_file = candidate_files[chosen_index]

    if buffer:
        buffer_and_play(
            info_hash=info_hash,
            file_id=chosen_file.get("id"),
            path=chosen_file.get("path"),
        )
    else:
        play(
            info_hash=info_hash,
            file_id=chosen_file.get("id"),
            path=chosen_file.get("path"),
        )


def wait_for_metadata(info_hash):
    close_busy_dialog()
    percent = 0
    timeout = get_metadata_timeout()
    start_time = time.time()
    monitor = Monitor()
    progress = DialogProgress()
    progress.create(ADDON_NAME, translate(30237))

    try:
        while api.get_torrent_info(info_hash).get("stat") == 1:
            if monitor.waitForAbort(0.5):
                raise PlayError("Abort requested")
            passed_time = time.time() - start_time
            if 0 < timeout:
                if timeout < passed_time:
                    notification(translate(30238))
                    raise PlayError("No metadata after timeout")
                percent = int(100 * passed_time / timeout)
            else:
                percent = 0 if percent == 100 else (percent + 5)
            progress.update(percent)
            if progress.iscanceled():
                raise CanceledError("User canceled metadata", info_hash)
    finally:
        progress.close()


@plugin.route("/buffer_and_play")
@query_arg("info_hash")
@query_arg("file_id")
@query_arg("path")
@check_playable
def buffer_and_play(info_hash, file_id, path):
    preload_torrent(info_hash, file_id)
    info = api.get_torrent_info(info_hash)
    if info.get("stat") == 1:
        wait_for_metadata(info_hash)
    wait_for_buffering_completion(info_hash, file_id)
    play(info_hash=info_hash, file_id=file_id, path=path)


def preload_torrent(info_hash, file_id):
    thread = Thread(target=api.preload_torrent, args=(info_hash, file_id))
    thread.start()


def wait_for_buffering_completion(info_hash, file_id):
    close_busy_dialog()
    info = api.get_torrent_file_info(info_hash, file_id)
    of = translate(30244)
    timeout = get_buffering_timeout()
    start_time = time.time()

    monitor = Monitor()
    progress = DialogProgress()
    progress.create(ADDON_NAME)

    try:
        while True:
            current_time = time.time()
            status = api.get_torrent_file_info(info_hash, file_id)
            preloaded_bytes = status.get("preloaded_bytes", 0)
            preload_size = status.get("preload_size", 0)

            if preloaded_bytes != 0 and preload_size != 0:
                if preloaded_bytes >= preload_size:
                    break

            if preload_size != 0:
                buffering_progress = preloaded_bytes * 100 / preload_size
            else:
                buffering_progress = 0

            speed = status.get("download_speed", 0)
            name = info.get("name")

            progress.update(
                int(buffering_progress),
                "{} - {:.2f}%\n{} {} {} - {}/s\n{}\n".format(
                    get_state_string(status.get("stat")),
                    buffering_progress,
                    sizeof_fmt(preloaded_bytes),
                    of,
                    sizeof_fmt(preload_size),
                    sizeof_fmt(speed),
                    name,
                ),
            )

            if progress.iscanceled():
                api.drop_torrent(info_hash)
                raise CanceledError("User canceled buffering", info_hash, name)
            if 0 < timeout < current_time - start_time:
                notification(translate(30236))
                api.drop_torrent(info_hash)
                raise PlayError("Buffering timeout reached")
            if monitor.waitForAbort(1):
                api.drop_torrent(info_hash)
                raise PlayError("Abort requested")
    finally:
        progress.close()


@plugin.route("/play")
@query_arg("info_hash")
@query_arg("file_id")
@query_arg("path")
@check_playable
def play(info_hash, file_id, path):
    name = path
    serve_url = api.get_stream_url(link=info_hash, path=name, file_id=file_id)
    setResolvedUrl(plugin.handle, True, ListItem(name, path=serve_url))

    try:
        with JackTorrPlayer(
            text_handler=(
                (lambda: get_status_labels(info_hash) + (name,))
                if show_status_overlay()
                else None
            ),
            on_close_handler=lambda: handle_player_stop(info_hash, name=name),
        ) as player:
            player.handle_events(url=serve_url)
    except Exception as e:
        logging.error("Caught exception while playing file: %s", e, exc_info=True)


@plugin.route("/insert")
def dialog_insert():
    window = DialogInsert("DialogInsert.xml", ADDON_PATH, "Default")
    window.doModal()
    if window.type == DialogInsert.TYPE_URL:
        api.add_magnet(window.ret_val)
    elif window.type == DialogInsert.TYPE_PATH:
        api.add_torrent(window.ret_val)
    else:
        return
    notification(translate(30243), time=2000)


def run():
    try:
        plugin.run()
    except Exception as e:
        logging.error("Caught exception:", exc_info=True)
        notification(str(e))
