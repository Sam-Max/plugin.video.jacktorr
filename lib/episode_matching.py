import re


_STRONG_PATTERNS = (
    re.compile(
        r"(?<![A-Za-z0-9])s0*(?P<season>[0-9]+)[ ._-]*e0*(?P<episode>[0-9]+)(?![0-9])",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![A-Za-z0-9])(?P<season>[0-9]+)[ ._-]*x[ ._-]*(?P<episode>[0-9]+)(?![0-9])",
        re.IGNORECASE,
    ),
)
_EPISODE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:episode|ep)[ ._-]*(?P<episode>[0-9]+)(?![0-9])",
    re.IGNORECASE,
)
_SEASON_PATTERNS = (
    re.compile(
        r"(?<![A-Za-z0-9])season[ ._-]*(?P<season>[0-9]+)(?![0-9])",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![A-Za-z0-9])s0*(?P<season>[0-9]+)(?![0-9])",
        re.IGNORECASE,
    ),
)


def _normalize_number(value):
    if isinstance(value, bool) or value is None:
        return None
    value = str(value).strip()
    if not re.fullmatch(r"[0-9]+", value):
        return None
    return int(value)


def _has_strong_match(path, season, episode):
    for pattern in _STRONG_PATTERNS:
        for match in pattern.finditer(path):
            if (
                int(match.group("season")) == season
                and int(match.group("episode")) == episode
                and not re.match(
                    r"(?:[ ._]*e0*[0-9]+|[ ._]*-[ ._]*(?:e0*[0-9]+|s0*[0-9]+[ ._-]*e0*[0-9]+|0*[0-9]+(?![A-Za-z0-9])))",
                    path[match.end() :],
                    re.IGNORECASE,
                )
            ):
                return True
    return False


def _season_contexts(text):
    contexts = set()
    for pattern in _SEASON_PATTERNS:
        contexts.update(int(match.group("season")) for match in pattern.finditer(text))
    return contexts


def _has_matching_season_context(path, torrent_title, season):
    path_contexts = _season_contexts(path)
    title_contexts = _season_contexts(torrent_title)
    contexts = path_contexts | title_contexts
    if not contexts or season not in contexts:
        return False
    return path_contexts.issubset({season}) and title_contexts.issubset({season})


def _has_episode_only_match(path, torrent_title, season, episode):
    if not _has_matching_season_context(path, torrent_title, season):
        return False
    return any(
        int(match.group("episode")) == episode
        for match in _EPISODE_PATTERN.finditer(path)
    )


def match_episode_file(candidate_files, season, episode, torrent_title=""):
    """Return one unambiguous candidate matching the requested TV episode."""
    season = _normalize_number(season)
    episode = _normalize_number(episode)
    if season is None or episode is None:
        return None

    torrent_title = str(torrent_title or "")
    matches = []
    for candidate in candidate_files:
        path = candidate.get("path", "") if isinstance(candidate, dict) else ""
        if not isinstance(path, str):
            continue
        if _has_strong_match(path, season, episode):
            matches.append((2, candidate))
        elif _has_episode_only_match(path, torrent_title, season, episode):
            matches.append((1, candidate))

    if not matches:
        return None

    best_score = max(score for score, _ in matches)
    best_matches = [candidate for score, candidate in matches if score == best_score]
    if len(best_matches) != 1:
        return None
    return best_matches[0]
