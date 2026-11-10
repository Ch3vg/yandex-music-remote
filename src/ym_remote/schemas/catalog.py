from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ym_remote.models.music import (
    Album,
    Artist,
    ArtistDetail,
    FamiliarTracks,
    Playlist,
    SearchView,
    Track,
    TrackPage,
)


class ArtistRefWire(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    name: str
    cover_url: str | None = None

    @classmethod
    def from_artist(cls, artist: Artist) -> ArtistRefWire:
        return cls(
            id=artist.id,
            name=artist.name,
            cover_url=artist.cover.list_url() if artist.cover else None,
        )


class CatalogTrackWire(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None
    album_id: int | None
    title: str
    artist: str
    cover_url: str
    cover_url_hq: str
    artists: list[ArtistRefWire] = Field(default_factory=list)

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
            artists=[ArtistRefWire.from_artist(artist) for artist in track.artists],
        )


class ArtistCardWire(BaseModel):
    id: int
    name: str
    cover_url: str | None = None
    cover_url_hq: str | None = None

    @classmethod
    def from_artist(cls, artist: Artist) -> ArtistCardWire:
        return cls(
            id=artist.id or 0,
            name=artist.name,
            cover_url=artist.cover.list_url() if artist.cover else None,
            cover_url_hq=artist.cover.hq_url() if artist.cover else None,
        )


class AlbumCardWire(BaseModel):
    id: int
    title: str
    artist: str
    year: int | None = None
    album_type: str | None = None
    version: str | None = None
    track_count: int = 0
    cover_url: str | None = None
    cover_url_hq: str | None = None

    @classmethod
    def from_album(cls, album: Album, *, fallback_artist: str = "") -> AlbumCardWire:
        return cls(
            id=album.id or 0,
            title=album.title,
            artist=album.artist_line() or fallback_artist,
            year=album.year,
            album_type=album.album_type,
            version=album.version,
            track_count=album.track_count,
            cover_url=album.cover.list_url() if album.cover else None,
            cover_url_hq=album.cover.hq_url() if album.cover else None,
        )


class AlbumDetailWire(BaseModel):
    id: int
    title: str
    artist: str
    artists: list[ArtistRefWire] = Field(default_factory=list)
    year: int | None = None
    album_type: str | None = None
    version: str | None = None
    track_count: int = 0
    cover_url: str | None = None
    cover_url_hq: str | None = None
    tracks: list[CatalogTrackWire] = Field(default_factory=list)

    @classmethod
    def from_album(cls, album: Album) -> AlbumDetailWire:
        return cls(
            id=album.id or 0,
            title=album.title,
            artist=album.artist_line(),
            artists=[ArtistRefWire.from_artist(artist) for artist in album.artists],
            year=album.year,
            album_type=album.album_type,
            version=album.version,
            track_count=album.track_count or len(album.tracks),
            cover_url=album.cover.list_url() if album.cover else None,
            cover_url_hq=album.cover.hq_url() if album.cover else None,
            tracks=[CatalogTrackWire.from_track(track) for track in album.tracks],
        )


class ArtistDetailWire(BaseModel):
    id: int
    name: str
    cover_url: str | None = None
    cover_url_hq: str | None = None
    ambient_color: str | None = None
    total_tracks: int = 0
    total_albums: int = 0
    popular_tracks: list[CatalogTrackWire] = Field(default_factory=list)
    familiar_total: int = 0
    albums: list[AlbumCardWire] = Field(default_factory=list)
    singles: list[AlbumCardWire] = Field(default_factory=list)

    @classmethod
    def from_detail(cls, detail: ArtistDetail) -> ArtistDetailWire:
        return cls(
            id=detail.id,
            name=detail.name,
            cover_url=detail.cover.list_url() if detail.cover else None,
            cover_url_hq=detail.cover.hq_url() if detail.cover else None,
            ambient_color=detail.ambient_color,
            total_tracks=detail.total_tracks,
            total_albums=detail.total_albums,
            popular_tracks=[CatalogTrackWire.from_track(track) for track in detail.popular_tracks],
            familiar_total=detail.familiar_total,
            albums=[
                AlbumCardWire.from_album(album, fallback_artist=detail.name)
                for album in detail.albums
                if album.id is not None
            ],
            singles=[
                AlbumCardWire.from_album(single, fallback_artist=detail.name)
                for single in detail.singles
                if single.id is not None
            ],
        )


class ArtistTracksPageWire(BaseModel):
    tracks: list[CatalogTrackWire] = Field(default_factory=list)
    page: int = 0
    page_size: int = 50
    total: int = 0
    has_more: bool = False

    @classmethod
    def from_page(cls, page: TrackPage) -> ArtistTracksPageWire:
        return cls(
            tracks=[CatalogTrackWire.from_track(track) for track in page.tracks],
            page=page.page,
            page_size=page.page_size,
            total=page.total,
            has_more=page.has_more,
        )


class ArtistFamiliarWire(BaseModel):
    collection_tracks: list[CatalogTrackWire] = Field(default_factory=list)
    wave_tracks: list[CatalogTrackWire] = Field(default_factory=list)
    tracks: list[CatalogTrackWire] = Field(default_factory=list)

    @classmethod
    def from_familiar(cls, familiar: FamiliarTracks) -> ArtistFamiliarWire:
        collection = [CatalogTrackWire.from_track(track) for track in familiar.collection]
        wave = [CatalogTrackWire.from_track(track) for track in familiar.wave]
        combined = [CatalogTrackWire.from_track(track) for track in familiar.all_tracks()]
        return cls(
            collection_tracks=collection,
            wave_tracks=wave,
            tracks=combined,
        )


class SearchResponseWire(BaseModel):
    artists: list[ArtistCardWire] = Field(default_factory=list)
    tracks: list[CatalogTrackWire] = Field(default_factory=list)

    @classmethod
    def from_view(cls, view: SearchView) -> SearchResponseWire:
        return cls(
            artists=[
                ArtistCardWire.from_artist(artist)
                for artist in view.artists
                if artist.id is not None
            ],
            tracks=[CatalogTrackWire.from_track(track) for track in view.tracks],
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
