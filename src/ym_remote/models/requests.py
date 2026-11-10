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
