from lib.torrserver.api import TorrServer


client = TorrServer(host="127.0.0.1", port=5665)
print(client.torr_version)

# print(
#     client.add_magnet(
#         magnet="magnet:?xt=urn:btih:aa47e75bfb6a47b5ba665087b4a17848c055a695&dn=Adventure.Gold.Diggers.S01E02.XviD-AFG%5BEZTVx.to%5D.avi%5Beztv%5D&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337%2Fannounce&tr=udp%3A%2F%2Fp4p.arenabg.com%3A1337%2Fannounce&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce&tr=udp%3A%2F%2Fopen.stealth.si%3A80%2Fannounce",
#         title="Adventure Gold Diggers S01E02 XviD-AFG EZTV",
#     )
# )

# for torrent in client.torrents():
#     print(torrent)


# 'stat': 1, 'stat_string': 'Torrent getting info'
# 'stat': 5, 'stat_string': 'Torrent in db'
# 'stat': 3, 'stat_string': 'Torrent working',

print(client.get_torrent_info(link="aa47e75bfb6a47b5ba665087b4a17848c055a695"))