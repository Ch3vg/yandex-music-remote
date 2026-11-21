from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayRequest:
    """Команда над конкретным треком. Числовой id Яндекса, не ключ бара."""

    track_id: int
    album_id: int | None = None
    title: str = ""
    artist: str = ""
    playlist_kind: int | None = None
    playlist_uid: int | None = None
    playlist_uuid: str | None = None
    playlist_track_index: int | None = None
    artist_id: int | None = None
    artist_mode: str | None = None
    context_album_id: int | None = None


@dataclass(frozen=True)
class WaveRequest:
    """Запуск уже существующего контекста волны в десктопном приложении."""

    source: str
    track_id: int | None = None
    album_id: int | None = None
    artist_id: int | None = None
    playlist_uuid: str | None = None
    playlist_kind: int | None = None
    playlist_uid: int | None = None
    prompt: str = ""
    card_title: str | None = None
    card_index: int | None = None
