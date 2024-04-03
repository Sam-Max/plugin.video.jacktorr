from lib.kodi import (
    get_int_setting,
    get_boolean_setting,
    get_setting,
    set_boolean_setting,
)


def get_service_host():
    return get_setting("service_host")


def get_port():
    return get_int_setting("service_port")


def get_metadata_timeout():
    return get_int_setting("metadata_timeout")


def get_buffering_timeout():
    return get_int_setting("buffer_timeout")


def show_status_overlay():
    return get_boolean_setting("overlay")


def get_min_candidate_size():
    return get_int_setting("min_candidate_size")


def ask_to_delete_torrent():
    return get_boolean_setting("ask_to_delete")


def service_enabled():
    return get_boolean_setting("service_enabled")


def set_service_enabled(value):
    set_boolean_setting("service_enabled", value)


def ssl_enabled():
    return get_boolean_setting("ssl_connection")


def get_username():
    return get_setting("service_login")


def get_password():
    return get_setting("service_password")


def get_files_order():
    return get_int_setting("files_order")


