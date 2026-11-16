from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ym_remote.models.requests import PlayRequest


class PlayCommand(BaseModel):
    """Команда воспроизведения. track_id — числовой id Яндекса."""

    model_config = ConfigDict(extra="ignore")

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

    def to_request(self) -> PlayRequest:
        return PlayRequest(
            track_id=self.track_id,
            album_id=self.album_id,
            title=self.title,
            artist=self.artist,
            playlist_kind=self.playlist_kind,
            playlist_uid=self.playlist_uid,
            playlist_uuid=self.playlist_uuid or None,
            playlist_track_index=self.playlist_track_index,
            artist_id=self.artist_id if self.artist_id and self.artist_id > 0 else None,
            artist_mode=self.artist_mode or None,
            context_album_id=(
                self.context_album_id
                if self.context_album_id and self.context_album_id > 0
                else None
            ),
        )
