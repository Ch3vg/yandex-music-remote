from ym_remote.yandex.map import track_from_api


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


def test_explicit_album_id_wins_over_the_cover_hint():
    cover = "avatars.yandex.net/get-music-content/103235/947055b7.a.3938372-1/%%"
    track = track_from_api(
        _Track(72529580, [_Album(9, "Real")], artists=(_Artist("Ghostemane", _Cover(cover)),))
    )
    assert track.album_id() == 9
