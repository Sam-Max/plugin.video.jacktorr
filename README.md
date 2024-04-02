# plugin.video.jacktorr

JackTorr is an torrent streaming engine for Kodi that implements [TorrServer](https://github.com/YouROK/TorrServer), which provides several features like an http API, cache size adjustment, memory and disk streaming, etc


## Installation

To install the addon, get the [latest release](https://github.com/Sam-Max/plugin.video.jacktorr/releases/latest) from github.
**Do NOT use the `Download ZIP` button on this page.** 

## Calling jacktorr from other addon

One can call jacktorr from other addons. To do so, simply use jacktorr API:

|Url|Description|
|---|-----------|
|`plugin://plugin.video.jacktorr/play_magnet?magnet=<magnet>`|Plays the provided `<magnet>`|
|`plugin://plugin.video.jacktorr/play_url?url=<url>`|Plays the provided torrent file `<url>`|
|`plugin://plugin.video.jacktorr/play_path?path=<path>`|Plays the provided torrent file path `<path>`|
