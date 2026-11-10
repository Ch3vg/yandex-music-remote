from ym_remote.yandex.map import album_from_api, artist_from_api, track_from_api


class _Cover:
    def __init__(self, uri):
        self.uri = uri


class _Artist:
    def __init__(self, name, cover=None):
        self.name = name
        self.id = 1
        self.cover = cover


class _Album:
    def __init__(self, album_id, title=""):
        self.id = album_id
        self.title = title
        self.cover_uri = None


class _Track:
    def __init__(self, track_id, albums, artists=(), album_id=None, cover_uri=None):
        self.id = track_id
        self.title = "Fed Up"
        self.artists = list(artists)
        self.albums = albums
        self.album_id = album_id
        self.cover_uri = cover_uri
        self.og_image = None


def test_playlist_row_keeps_album_id_when_album_stubs_have_no_id():
    track = track_from_api(_Track(72529580, [_Album(None)]), fallback_album_id=3938372)
    assert track.id == 72529580
    assert track.album_id() == 3938372


def test_missing_album_id_is_recovered_from_the_artist_cover():
    cover = "avatars.yandex.net/get-music-content/103235/947055b7.a.3938372-1/%%"
    track = track_from_api(_Track("72529580", [], artists=(_Artist("Ghostemane", _Cover(cover)),)))
    assert track.id == 72529580
    assert track.album_id() == 3938372
    assert track.artist_line() == "Ghostemane"
    assert track.artists[0].cover is not None
    assert track.artists[0].cover.list_url() == (
        "https://avatars.yandex.net/get-music-content/103235/947055b7.a.3938372-1/200x200"
    )


def test_explicit_album_id_wins_over_the_cover_hint():
    cover = "avatars.yandex.net/get-music-content/103235/947055b7.a.3938372-1/%%"
    track = track_from_api(
        _Track(72529580, [_Album(9, "Real")], artists=(_Artist("Ghostemane", _Cover(cover)),))
    )
    assert track.album_id() == 9


def test_artist_from_api_extracts_id_name_and_fallback_covers():
    direct = artist_from_api(
        {"id": "41052", "name": "  Кино ", "cover": {"uri": "avatars.yandex.net/art/%%"}}
    )
    assert direct.id == 41052
    assert direct.name == "Кино"
    assert direct.cover is not None
    assert direct.cover.hq_url() == "https://avatars.yandex.net/art/1000x1000"

    og = artist_from_api({"id": 77, "name": "DDT", "og_image": "avatars.yandex.net/og/%%"})
    assert og.id == 77
    assert og.cover is not None
    assert og.cover.list_url() == "https://avatars.yandex.net/og/200x200"

    from_fallback = artist_from_api(
        {"id": 88, "name": "Сплин", "cover": None},
        fallback_covers=[{"items_uri": ["avatars.yandex.net/all/%%"]}],
    )
    assert from_fallback.id == 88
    assert from_fallback.cover is not None
    assert from_fallback.cover.source == "avatars.yandex.net/all/%%"


def test_album_from_api_flattens_volumes_and_inherits_cover_and_artists():
    raw_album = {
        "id": 9001,
        "title": "In Rainbows",
        "year": 2007,
        "type": "single",
        "version": "Bonus Edition",
        "track_count": 3,
        "cover_uri": "avatars.yandex.net/alb/%%",
        "artists": [{"id": 36800, "name": "Radiohead"}],
        "volumes": [
            [
                {"id": 101, "title": "15 Step", "artists": [], "albums": []},
                {
                    "id": 102,
                    "title": "Bodysnatchers",
                    "artists": [{"id": 36800, "name": "Radiohead"}, {"id": 99, "name": "Guest"}],
                    "cover_uri": "avatars.yandex.net/custom/%%",
                },
            ],
            [
                {"id": 103, "title": "Nude"},
            ],
        ],
    }
    album = album_from_api(raw_album)
    assert album.id == 9001
    assert album.title == "In Rainbows"
    assert album.year == 2007
    assert album.album_type == "single"
    assert album.version == "Bonus Edition"
    assert album.track_count == 3
    assert album.artist_line() == "Radiohead"
    assert [t.id for t in album.tracks] == [101, 102, 103]
    assert [t.playlist_index for t in album.tracks] == [0, 1, 2]
    assert all(t.album_id() == 9001 for t in album.tracks)
    assert album.tracks[0].artist_line() == "Radiohead"
    assert album.tracks[0].cover is not None
    assert album.tracks[0].cover.source == "avatars.yandex.net/alb/%%"
    assert album.tracks[1].artist_line() == "Radiohead, Guest"
    assert album.tracks[1].cover is not None
    assert album.tracks[1].cover.source == "avatars.yandex.net/custom/%%"
