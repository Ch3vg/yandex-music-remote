import pytest
from pydantic import ValidationError

from ym_remote.models.music import (
    Album,
    Artist,
    ArtistDetail,
    Cover,
    FamiliarTracks,
    Playlist,
    SearchView,
    Track,
    TrackPage,
)
from ym_remote.models.playback import NowMeta, Playback, QueueItem, QueueView
from ym_remote.schemas.catalog import (
    AlbumDetailWire,
    ArtistDetailWire,
    ArtistFamiliarWire,
    ArtistTracksPageWire,
    CatalogTrackWire,
    HomeWire,
    LikesWire,
    PlaylistCardWire,
    PlaylistDetailWire,
    SearchResponseWire,
)
from ym_remote.schemas.play import PlayCommand
from ym_remote.schemas.playback import PlaybackWire, playback_message
from ym_remote.schemas.queue import queue_message
from ym_remote.services.texts import queue_notice


def test_playback_track_id_is_the_change_key_string():
    playback = Playback(
        title="Song",
        artist="A, B",
        is_playing=True,
        cover_url="https://cdn/cover/200x200",
        cover_url_hq="https://cdn/cover/1000x1000",
        volume=15,
        artist_href="/artist/1",
        album_href=None,
        position_sec=3.5,
        duration_sec=200,
        repeat_mode="one",
        shuffle=True,
        liked=False,
        queue_name="Плейлист",
    )
    payload = playback_message("now_playing", playback)
    assert payload["type"] == "now_playing"
    assert payload["track_id"] == "A, B|Song"
    assert isinstance(payload["track_id"], str)
    assert payload["album_href"] is None
    assert set(PlaybackWire.model_fields) <= set(payload)
    tick = playback_message("player_tick", playback)
    assert tick["type"] == "player_tick"
    assert tick["track_id"] == payload["track_id"]


def test_play_command_track_id_is_numeric_and_not_the_bar_key():
    command = PlayCommand.model_validate(
        {
            "command": "play_now",
            "track_id": 123,
            "album_id": 456,
            "title": "",
            "artist": "",
            "playlist_kind": 3,
            "playlist_uid": 1,
            "playlist_uuid": "uuid",
            "playlist_track_index": 0,
        }
    )
    request = command.to_request()
    assert request.track_id == 123
    assert isinstance(request.track_id, int)
    assert request.playlist_uuid == "uuid"
    with pytest.raises(ValidationError):
        PlayCommand.model_validate({"track_id": "A, B|Song"})


def test_catalog_and_queue_json():
    track = Track(
        id=1,
        title="Song",
        artists=(Artist("A"), Artist("B")),
        albums=(Album(2, "Album"),),
        cover=Cover("cdn.example/%%"),
        playlist_index=4,
    )
    dumped = CatalogTrackWire.from_track(track).model_dump()
    assert dumped == {
        "id": 1,
        "album_id": 2,
        "title": "Song",
        "artist": "A, B",
        "cover_url": "https://cdn.example/200x200",
        "cover_url_hq": "https://cdn.example/1000x1000",
        "artists": [
            {"id": None, "name": "A", "cover_url": None},
            {"id": None, "name": "B", "cover_url": None},
        ],
    }
    assert "playlist_index" not in dumped
    home = HomeWire(
        likes=LikesWire(
            title="Мне нравится",
            tracks=[],
            kind=3,
            uid=1,
            playlist_uuid=None,
            track_count=0,
            cover_url=None,
        ),
        playlists=[
            PlaylistCardWire.from_playlist(
                Playlist(kind=5, uid=9, uuid="p", title="Рок", track_count=2, cover=None)
            )
        ],
    )
    assert home.model_dump()["likes"]["title"] == "Мне нравится"
    assert home.model_dump()["playlists"][0]["is_likes"] is False
    detail = PlaylistDetailWire.from_playlist(
        Playlist(kind=3, uid=1, uuid=None, title="Мне нравится", track_count=1, tracks=(track,))
    )
    assert list(detail.model_dump()) == ["kind", "uid", "playlist_uuid", "title", "tracks"]
    current = QueueItem(track=track, is_playing=True, is_current=True)
    message = queue_message(
        QueueView(before=(), current=current, after=(), now_meta=NowMeta("Сейчас", "Волна"))
    )
    assert message["type"] == "queue"
    assert message["before"] == []
    assert message["current"]["is_current"] is True
    assert message["current"]["track_id"] == 1
    assert message["before_title"] == "Предыдущая очередь"


def test_queue_notice_omits_empty_artist_and_title():
    assert queue_notice("A", "Song", end=False) == "Трек A — Song — играть следующим"
    assert queue_notice("A", "Song", end=True) == "Трек A — Song — в конец очереди"
    assert queue_notice("", "", end=False) == "Трек  — играть следующим"
    assert queue_notice("A", "", end=False) == "Трек A — играть следующим"


def test_artist_album_tracks_and_search_wire_serialization():
    artist_a = Artist(name="Radiohead", id=36800, cover=Cover("cdn.example/art/%%"))
    artist_b = Artist(name="Thom Yorke", id=1020)
    track = Track(
        id=99,
        title="Everything In Its Right Place",
        artists=(artist_a, artist_b),
        albums=(Album(id=500, title="Kid A"),),
        cover=Cover("cdn.example/trk/%%"),
    )
    album = Album(
        id=500,
        title="Kid A",
        cover=Cover("cdn.example/alb/%%"),
        year=2000,
        album_type=None,
        version="Remastered",
        track_count=10,
        artists=(artist_a,),
        tracks=(track,),
    )
    single = Album(
        id=501,
        title="Pyramid Song",
        cover=Cover("cdn.example/sng/%%"),
        year=2001,
        album_type="single",
        track_count=1,
    )
    detail = ArtistDetail(
        id=36800,
        name="Radiohead",
        cover=Cover("cdn.example/art/%%"),
        ambient_color="#5bbdd6",
        total_tracks=150,
        total_albums=12,
        popular_tracks=(track,),
        familiar_total=7,
        albums=(album, Album(id=None, title="Broken")),
        singles=(single,),
    )

    artist_wire = ArtistDetailWire.from_detail(detail).model_dump()
    assert artist_wire["id"] == 36800
    assert artist_wire["name"] == "Radiohead"
    assert artist_wire["cover_url"] == "https://cdn.example/art/200x200"
    assert artist_wire["cover_url_hq"] == "https://cdn.example/art/1000x1000"
    assert artist_wire["ambient_color"] == "#5bbdd6"
    assert artist_wire["familiar_total"] == 7
    assert len(artist_wire["popular_tracks"]) == 1
    assert artist_wire["popular_tracks"][0]["artists"] == [
        {"id": 36800, "name": "Radiohead", "cover_url": "https://cdn.example/art/200x200"},
        {"id": 1020, "name": "Thom Yorke", "cover_url": None},
    ]
    assert len(artist_wire["albums"]) == 1
    assert artist_wire["albums"][0]["id"] == 500
    assert artist_wire["albums"][0]["artist"] == "Radiohead"
    assert len(artist_wire["singles"]) == 1
    assert artist_wire["singles"][0]["artist"] == "Radiohead"
    assert artist_wire["singles"][0]["album_type"] == "single"

    album_wire = AlbumDetailWire.from_album(album).model_dump()
    assert album_wire["id"] == 500
    assert album_wire["artist"] == "Radiohead"
    assert album_wire["artists"] == [
        {"id": 36800, "name": "Radiohead", "cover_url": "https://cdn.example/art/200x200"}
    ]
    assert album_wire["year"] == 2000
    assert album_wire["version"] == "Remastered"
    assert album_wire["track_count"] == 10
    assert len(album_wire["tracks"]) == 1

    page_wire = ArtistTracksPageWire.from_page(
        TrackPage(tracks=(track,), page=1, page_size=50, total=120, has_more=True)
    ).model_dump()
    assert page_wire["page"] == 1
    assert page_wire["page_size"] == 50
    assert page_wire["total"] == 120
    assert page_wire["has_more"] is True
    assert len(page_wire["tracks"]) == 1

    wave_track = Track(
        id=100,
        title="Idioteque",
        artists=(artist_a,),
        albums=(Album(id=500, title="Kid A"),),
    )
    familiar_wire = ArtistFamiliarWire.from_familiar(
        FamiliarTracks(collection=(track,), wave=(track, wave_track))
    ).model_dump()
    assert [t["id"] for t in familiar_wire["collection_tracks"]] == [99]
    assert [t["id"] for t in familiar_wire["wave_tracks"]] == [99, 100]
    assert [t["id"] for t in familiar_wire["tracks"]] == [99, 100]

    search_wire = SearchResponseWire.from_view(
        SearchView(
            artists=(artist_a, Artist(name="NoId", id=None)),
            tracks=(track,),
        )
    ).model_dump()
    assert search_wire["artists"] == [
        {
            "id": 36800,
            "name": "Radiohead",
            "cover_url": "https://cdn.example/art/200x200",
            "cover_url_hq": "https://cdn.example/art/1000x1000",
        }
    ]
    assert len(search_wire["tracks"]) == 1


def test_play_command_supports_artist_and_album_contexts_and_playback_artists():
    cmd_artist = PlayCommand.model_validate(
        {
            "command": "play_now",
            "track_id": 55,
            "album_id": 66,
            "artist_id": 36800,
            "artist_mode": "familiar_wave",
            "playlist_track_index": 2,
        }
    ).to_request()
    assert cmd_artist.artist_id == 36800
    assert cmd_artist.artist_mode == "familiar_wave"
    assert cmd_artist.playlist_track_index == 2

    cmd_album = PlayCommand.model_validate(
        {
            "command": "play_next",
            "track_id": 55,
            "context_album_id": 700,
            "artist_id": 0,
        }
    ).to_request()
    assert cmd_album.context_album_id == 700
    assert cmd_album.artist_id is None

    playback = Playback(
        title="Track",
        artist="A, B",
        is_playing=True,
        cover_url=None,
        cover_url_hq=None,
        volume=50,
        artist_href="/artist?artistId=10",
        album_href=None,
        position_sec=0,
        duration_sec=120,
        repeat_mode="off",
        shuffle=False,
        liked=False,
        queue_name="",
        artists=(Artist(name="A", id=10, cover=Cover("cdn.example/a/%%")), Artist(name="B", id=20)),
    )
    msg = playback_message("now_playing", playback)
    assert msg["artists"] == [
        {"id": 10, "name": "A", "cover_url": "https://cdn.example/a/200x200"},
        {"id": 20, "name": "B", "cover_url": None},
    ]

    q_item = QueueItem(
        track=Track(id=7, title="Q", artists=(Artist(name="A", id=10, cover=Cover("cdn.example/a/%%")),)),
        is_playing=False,
    )
    q_msg = queue_message(QueueView(after=(q_item,)))
    assert q_msg["after"][0]["artists"] == [
        {"id": 10, "name": "A", "cover_url": "https://cdn.example/a/200x200"}
    ]
