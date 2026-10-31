# Changelog

All notable changes to JackTorr are documented in this file.

## 1.3.0

### Added
- Torznab search through TorrServer, with its own main-menu entry and search history.
- Torrent and file sizes displayed in torrent and file lists.
- An "All Torrents" entry and localized TorrServer category labels (Movies, Series, Music, Other).
- Separate settings to show or hide the Rutor and Torznab search entries.
- An "Enable Torznab Search" option in the TorrServer settings.

### Changed
- The Rutor search entry on the main menu is hidden by default and is enabled from the addon settings.
- Applying settings to TorrServer updates only addon-managed fields, preserving Torznab indexers and the rest of the server configuration.
- Updated Romanian translations.

### Fixed
- Search notifications now distinguish a provider that is disabled in TorrServer from a genuine empty result.
- Invalid or non-object TorrServer settings responses are rejected instead of overwriting server configuration.
- Plugin directory errors log the full traceback in kodi.log.

## 1.2.2

### Added
- Torrent lists are organized by categories, including uncategorized torrents.
- Display titles, descriptions, and posters are retained for added torrents.

## 1.2.1

### Fixed
- TorrServer settings are now correctly gated by the apply-settings option in Kodi.

## 1.2.0

### Added
- Rutor search with persistent recent-search history.
- Poster and category actions for torrent items.
- A dedicated magnifying-glass icon for Search.

### Changed
- Torrent file lists now focus on playable files and remove shared folder prefixes.
- An optional setting can hide subfolder names in torrent file lists.
- Requested season episodes are selected automatically when available.
- Settings are organized more clearly and include additional localizations.

### Fixed
- Buffering retries transient failures and TorrServer connection and error handling is more resilient.
- TorrServer settings synchronization updates only explicitly enabled options.

## 1.1.0
Baseline release.
