from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ym_remote.models.music import Playlist, Track


class CatalogTrackWire(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None
    album_id: int | None
    title: str
    artist: str
    cover_url: str
    cover_url_hq: str

    @classmethod
    def from_track(cls, track: Track) -> CatalogTrackWire:
        cover = track.cover.list_url() if track.cover else None
        hq = track.cover.hq_url() if track.cover else None
        return cls(
            id=track.id,
            album_id=track.album_id(),
            title=track.title,
            artist=track.artist_line(),
            cover_url=cover or "",
            cover_url_hq=hq or "",
        )


class PlaylistCardWire(BaseModel):
    kind: int | None
    uid: int | None
    playlist_uuid: str | None
    title: str
    track_count: int
    cover_url: str | None
    is_likes: bool

    @classmethod
    def from_playlist(cls, playlist: Playlist) -> PlaylistCardWire:
        cover = playlist.cover.list_url() if playlist.cover else None
        return cls(
            kind=playlist.kind,
            uid=playlist.uid,
            playlist_uuid=playlist.uuid,
            title=playlist.title,
            track_count=playlist.track_count,
            cover_url=cover,
            is_likes=playlist.is_likes,
        )


class LikesWire(BaseModel):
    title: str
    tracks: list[CatalogTrackWire]
    kind: int | None
    uid: int | None
    playlist_uuid: str | None
    track_count: int
    cover_url: str | None


class HomeWire(BaseModel):
    likes: LikesWire
    playlists: list[PlaylistCardWire]


class PlaylistDetailWire(BaseModel):
    kind: int | None
    uid: int | None
    playlist_uuid: str | None
    title: str
    tracks: list[CatalogTrackWire]

    @classmethod
    def from_playlist(cls, playlist: Playlist) -> PlaylistDetailWire:
        return cls(
            kind=playlist.kind,
            uid=playlist.uid,
            playlist_uuid=playlist.uuid,
            title=playlist.title,
            tracks=[CatalogTrackWire.from_track(track) for track in playlist.tracks],
        )
