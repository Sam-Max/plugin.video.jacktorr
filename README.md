# plugin.video.jacktorr

JackTorr is an torrent streaming engine for Kodi that implements [TorrServer](https://github.com/YouROK/TorrServer), which provides several features like an http API for streaming, memory and disk cache, API auth, etc

**NOTE**: The addon has not inbuilt TorrServer daemon, so you need to deploy externally and configure server on Jacktorr settings.

## Installation

To install the addon, get the [latest release](https://github.com/Sam-Max/plugin.video.jacktorr/releases/latest) from github.
**Do NOT use the `Download ZIP` button on this page.** 

## Docker Compose

```
version: '3.3'
services:
    torrserver:
        image: ghcr.io/yourok/torrserver
        container_name: torrserver
        environment:
            - TS_PORT=5665
            - TS_DONTKILL=1
            - TS_HTTPAUTH=0
            - TS_CONF_PATH=/opt/ts/config
            - TS_TORR_DIR=/opt/ts/torrents
        volumes:
            - './CACHE:/opt/ts/torrents'
            - './CONFIG:/opt/ts/config'
        ports:
            - '5665:5665'
        restart: unless-stopped
```

## Calling jacktorr from other addon

One can call jacktorr from other addons. To do so, simply use jacktorr API:

|Url|Description|
|---|-----------|
|`plugin://plugin.video.jacktorr/play_magnet?magnet=<magnet>`|Plays the provided `<magnet>`|
|`plugin://plugin.video.jacktorr/play_url?url=<url>`|Plays the provided torrent file `<url>`|
|`plugin://plugin.video.jacktorr/play_path?path=<path>`|Plays the provided torrent file path `<path>`|
