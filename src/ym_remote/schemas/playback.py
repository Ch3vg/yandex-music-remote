from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ym_remote.models.playback import Playback

RepeatMode = Literal["off", "queue", "one"]


class PlaybackWire(BaseModel):
    """Снимок бара. track_id — строка «артист|название», не id Яндекса."""

    model_config = ConfigDict(extra="ignore")

    track_id: str
    title: str
    artist: str
    is_playing: bool
    cover_url: str | None = None
    cover_url_hq: str | None = None
    volume: int | None = None
    artist_href: str | None = None
    album_href: str | None = None
    position_sec: float | None = None
    duration_sec: float | None = None
    repeat_mode: RepeatMode = "off"
    shuffle: bool = False
    liked: bool = False
    queue_name: str = ""

    @classmethod
    def from_playback(cls, playback: Playback) -> PlaybackWire:
        mode: RepeatMode = "off"
        if playback.repeat_mode in ("off", "queue", "one"):
            mode = playback.repeat_mode  # type: ignore[assignment]
        return cls(
            track_id=playback.track_key(),
            title=playback.title,
            artist=playback.artist,
            is_playing=playback.is_playing,
            cover_url=playback.cover_url,
            cover_url_hq=playback.cover_url_hq,
            volume=playback.volume,
            artist_href=playback.artist_href,
            album_href=playback.album_href,
            position_sec=playback.position_sec,
            duration_sec=playback.duration_sec,
            repeat_mode=mode,
            shuffle=playback.shuffle,
            liked=playback.liked,
            queue_name=playback.queue_name,
        )


def playback_message(kind: str, playback: Playback) -> dict:
    payload = PlaybackWire.from_playback(playback).model_dump()
    payload["type"] = kind
    return payload
