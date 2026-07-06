from __future__ import annotations

import json
import logging
import os

from lib.kodi import ADDON_DATA


def _history_path() -> str:
    return os.path.join(ADDON_DATA, "search_history.json")


def load_history() -> list[str]:
    path = _history_path()
    try:
        with open(path, "r", encoding="utf-8") as file:
            history = json.load(file)
    except (OSError, ValueError, TypeError):
        return []

    if not isinstance(history, list):
        return []

    return [term for term in history if isinstance(term, str)]


def add_search(term: str) -> None:
    term = (term or "").strip()
    if not term:
        return

    path = _history_path()
    tmp_path = path + ".tmp"
    try:
        os.makedirs(ADDON_DATA, exist_ok=True)
        history = [item for item in load_history() if item != term]
        history.insert(0, term)
        history = history[:20]
        with open(tmp_path, "w", encoding="utf-8") as file:
            json.dump(history, file)
        os.replace(tmp_path, path)
    except Exception:
        logging.exception("Failed to persist search history")


def clear_history() -> None:
    path = _history_path()
    if not os.path.exists(path):
        return

    try:
        os.remove(path)
    except OSError:
        logging.exception("Failed to clear search history")
