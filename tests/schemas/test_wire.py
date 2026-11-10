import pytest
from pydantic import ValidationError

from ym_remote.models.music import Album, Artist, Cover, Playlist, Track
from ym_remote.models.playback import NowMeta, Playback, QueueItem, QueueView
from ym_remote.schemas.catalog import CatalogTrackWire, HomeWire, LikesWire, PlaylistCardWire, PlaylistDetailWire
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
