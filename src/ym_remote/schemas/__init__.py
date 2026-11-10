"""Проводной JSON из application.md.

Двойной смысл `track_id` живёт только здесь.
В снимке плеера это строка «артист|название» (ключ смены трека на пульте).
В командах воспроизведения это числовой идентификатор Яндекса.
Доменные модели эти поля не смешивают: Playback.track_key() и PlayRequest.track_id.
"""

from ym_remote.schemas.catalog import (
    AlbumCardWire,
    AlbumDetailWire,
    ArtistCardWire,
    ArtistDetailWire,
    ArtistFamiliarWire,
    ArtistRefWire,
    ArtistTracksPageWire,
    CatalogTrackWire,
    HomeWire,
    LikesWire,
    PlaylistCardWire,
    PlaylistDetailWire,
    SearchResponseWire,
)
from ym_remote.schemas.playback import PlaybackWire, playback_message
from ym_remote.schemas.play import PlayCommand
from ym_remote.schemas.queue import queue_message

__all__ = [
    "AlbumCardWire",
    "AlbumDetailWire",
    "ArtistCardWire",
    "ArtistDetailWire",
    "ArtistFamiliarWire",
    "ArtistRefWire",
    "ArtistTracksPageWire",
    "CatalogTrackWire",
    "HomeWire",
    "LikesWire",
    "PlayCommand",
    "PlaybackWire",
    "PlaylistCardWire",
    "PlaylistDetailWire",
    "SearchResponseWire",
    "playback_message",
    "queue_message",
]
