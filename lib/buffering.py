"""Pure helpers for buffering progress and retry decisions."""

import logging


LOGGER = logging.getLogger(__name__)

MAX_RETRIES_DEFAULT = 3
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_MAX_SECONDS = 8.0


def clamp_progress(value):
    """Clamp buffering progress to 0-100 int for DialogProgress.update."""
    if value < 0:
        return 0
    if value > 100:
        return 100
    return int(value)


def is_retryable_error(exc, *, retryable_status_none=True):
    """Return whether a TorrServerError should be retried."""
    from lib.torrserver.api import TorrServerError

    if not isinstance(exc, TorrServerError):
        return False
    code = getattr(exc, "status_code", None)
    if code is None:
        return retryable_status_none
    if code == 429:
        return True
    if 500 <= code < 600:
        return True
    return False


def backoff_seconds(attempt):
    """Exponential backoff: 1, 2, 4, 8 (capped). attempt is 0-based."""
    if attempt < 0:
        attempt = 0
    return min(BACKOFF_BASE_SECONDS * (2 ** attempt), BACKOFF_MAX_SECONDS)


def compute_buffering_progress(preloaded_bytes, preload_size):
    """Return clamped 0-100 progress for buffering status."""
    if not preload_size or preload_size <= 0:
        return 0
    if not preloaded_bytes or preloaded_bytes <= 0:
        return 0
    return clamp_progress(preloaded_bytes * 100.0 / preload_size)


def is_preload_complete(preloaded_bytes, preload_size):
    """Return whether preloading is complete with positive sizes only."""
    if not preload_size or preload_size <= 0:
        return False
    if not preloaded_bytes or preloaded_bytes <= 0:
        return False
    return preloaded_bytes >= preload_size


def is_resolving_metadata(preload_size):
    """Return whether TorrServer has not resolved preload metadata yet."""
    return not preload_size or preload_size <= 0
