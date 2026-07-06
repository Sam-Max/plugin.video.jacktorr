from lib.buffering import (
    backoff_seconds,
    clamp_progress,
    compute_buffering_progress,
    is_preload_complete,
    is_resolving_metadata,
    is_retryable_error,
)
from lib.torrserver.api import TorrServerError


def test_clamp_progress_clamps_and_converts_to_int():
    assert clamp_progress(-10) == 0
    assert clamp_progress(0) == 0
    assert clamp_progress(50) == 50
    assert clamp_progress(100) == 100
    assert clamp_progress(150) == 100
    assert clamp_progress(50.9) == 50


def test_is_retryable_error_matches_retry_policy():
    assert is_retryable_error(TorrServerError("network", status_code=None)) is True
    assert is_retryable_error(TorrServerError("503", status_code=503)) is True
    assert is_retryable_error(TorrServerError("500", status_code=500)) is True
    assert is_retryable_error(TorrServerError("429", status_code=429)) is True
    assert is_retryable_error(TorrServerError("401", status_code=401)) is False
    assert is_retryable_error(TorrServerError("404", status_code=404)) is False
    assert is_retryable_error(TorrServerError("legacy")) is True
    assert is_retryable_error(ValueError("not torr")) is False


def test_backoff_seconds_uses_capped_exponential_backoff():
    assert backoff_seconds(0) == 1.0
    assert backoff_seconds(1) == 2.0
    assert backoff_seconds(2) == 4.0
    assert backoff_seconds(3) == 8.0
    assert backoff_seconds(4) == 8.0
    assert backoff_seconds(-1) == 1.0


def test_compute_buffering_progress_clamps_to_valid_range():
    assert compute_buffering_progress(0, 0) == 0
    assert compute_buffering_progress(0, 100) == 0
    assert compute_buffering_progress(50, 100) == 50
    assert compute_buffering_progress(100, 100) == 100
    assert compute_buffering_progress(150, 100) == 100
    assert compute_buffering_progress(-10, 100) == 0


def test_is_preload_complete_requires_positive_sizes():
    assert is_preload_complete(0, 0) is False
    assert is_preload_complete(0, 100) is False
    assert is_preload_complete(100, 0) is False
    assert is_preload_complete(100, 100) is True
    assert is_preload_complete(150, 100) is True
    assert is_preload_complete(99, 100) is False


def test_is_resolving_metadata_detects_unresolved_preload_size():
    assert is_resolving_metadata(0) is True
    assert is_resolving_metadata(None) is True
    assert is_resolving_metadata(-5) is True
    assert is_resolving_metadata(100) is False
