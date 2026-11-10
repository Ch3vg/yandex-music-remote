from ym_remote.models.music import Album, Artist, Cover, Playlist, Track
from ym_remote.models.playback import Playback


def test_artists_are_joined_without_duplicates():
    track = Track(
        id=1,
        title="Song",
        artists=(Artist("A"), Artist("A"), Artist(" B "), Artist("")),
    )
    assert track.artist_line() == "A, B"
    assert track.change_key() == "A, B|Song"


def test_cover_list_and_hq_urls():
    cover = Cover("avatars.yandex.net/get-music-content/123/%%")
    assert cover.list_url() == "https://avatars.yandex.net/get-music-content/123/200x200"
    assert cover.hq_url() == "https://avatars.yandex.net/get-music-content/123/1000x1000"

    sized = Cover("https://cdn.example/foo/300x400")
    assert sized.list_url() == "https://cdn.example/foo/300x400"
    assert sized.hq_url() == "https://cdn.example/foo/1000x1000"

    assert Cover(None).list_url() is None
    assert Cover("").hq_url() is None


def test_likes_playlist_by_title_or_kind():
    assert Playlist(kind=3, uid=1, uuid=None, title="Другое", track_count=0).is_likes
    assert Playlist(kind=1, uid=1, uuid=None, title="Мне нравится", track_count=1).is_likes
    assert not Playlist(kind=1, uid=1, uuid=None, title="Рок", track_count=2).is_likes


def test_album_id_comes_from_the_first_album():
    track = Track(
        id=7,
        title="T",
        albums=(Album(None, ""), Album(42, "A")),
    )
    assert track.album_id() == 42


def test_now_playing_tuple_ignores_position():
    base = dict(
        title="Song",
        artist="A, B",
        is_playing=True,
        cover_url="https://cdn/1",
        cover_url_hq="https://cdn/1/1000x1000",
        volume=40,
        artist_href=None,
        album_href=None,
        duration_sec=180.0,
        repeat_mode="queue",
        shuffle=False,
        liked=True,
        queue_name="Мне нравится",
    )
    early = Playback(position_sec=1, **base)
    late = Playback(position_sec=40, **base)
    assert early.now_playing_tuple() == late.now_playing_tuple()
    assert early.track_key() == "A, B|Song"
    assert "position" not in str(early.now_playing_tuple())
