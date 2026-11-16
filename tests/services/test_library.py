import pytest

from ym_remote.models.errors import RemoteError
from ym_remote.models.music import (
    Album,
    Artist,
    ArtistDetail,
    Cover,
    FamiliarTracks,
    Playlist,
    Track,
    TrackPage,
)
from ym_remote.services.library import LibraryService, full_likes_count
from ym_remote.services.texts import ALBUM_NOT_FOUND, API_NOT_READY, ARTIST_NOT_FOUND, LIBRARY_FAILED


def test_full_likes_count_is_not_the_preview_length():
    assert full_likes_count(12, 12, 240) == 240
    assert full_likes_count(240, 12, 240) == 240
    assert full_likes_count(12, 12, 12) == 12
    assert full_likes_count(0, 12, 240) == 240
    assert full_likes_count(0, 0, 0) == 0


class Catalog:
    ready = True
    uid = 7

    def __init__(self, summary_count=240, listed_count=12, total=240, listed=True):
        self.summary_count = summary_count
        self.listed_count = listed_count
        self.total = total
        self.listed = listed
        self.summary_kind = None

    async def like_tracks(self, limit=12):
        size = min(limit, self.total)
        preview = tuple(Track(id=index, title=f"t{index}") for index in range(size))
        return preview, self.total

    async def playlists(self):
        rows = []
        if self.listed:
            rows.append(
                Playlist(
                    kind=3,
                    uid=7,
                    uuid="likes-list",
                    title="Мне нравится",
                    track_count=self.listed_count,
                    cover=Cover("%%"),
                )
            )
        rows.append(Playlist(kind=5, uid=7, uuid="rock", title="Рок", track_count=4, cover=None))
        return tuple(rows)

    async def playlist_summary(self, kind):
        self.summary_kind = kind
        return Playlist(
            kind=kind,
            uid=7,
            uuid="likes-full",
            title="Мне нравится",
            track_count=self.summary_count,
            cover=Cover("https://cover"),
        )


async def test_home_hero_uses_the_playlist_count_not_the_twelve_preview():
    catalog = Catalog()
    home = await LibraryService(catalog).home()
    assert catalog.summary_kind == 3
    assert len(home.tracks) == 12
    assert home.likes.track_count == 240
    assert home.likes.uuid == "likes-full"
    assert home.likes.uid == 7
    assert [item.title for item in home.playlists] == ["Рок"]


async def test_missing_likes_card_still_asks_the_playlist_for_kind_3():
    catalog = Catalog(listed=False)
    home = await LibraryService(catalog).home()
    assert catalog.summary_kind == 3
    assert home.likes.track_count == 240
    assert len(home.tracks) == 12


async def test_preview_sized_reported_count_yields_to_the_full_likes_list():
    catalog = Catalog(summary_count=12, listed_count=12, total=240)
    home = await LibraryService(catalog).home()
    assert home.likes.track_count == 240
    assert len(home.tracks) == 12


class _ArtistAlbumCatalog:
    def __init__(self, *, ready: bool = True, fail: bool = False):
        self.ready = ready
        self.fail = fail
        self.uid = 7

    async def artist_detail(self, artist_id: int):
        if self.fail:
            raise RuntimeError("boom")
        if artist_id == 404:
            return None
        return ArtistDetail(id=artist_id, name="Radiohead", familiar_total=3)

    async def artist_tracks(self, artist_id: int, page: int = 0, page_size: int = 50):
        if self.fail:
            raise RuntimeError("boom")
        return TrackPage(
            tracks=(Track(id=1, title="Creep"),),
            page=page,
            page_size=page_size,
            total=1,
            has_more=False,
        )

    async def artist_familiar(self, artist_id: int):
        if self.fail:
            raise RuntimeError("boom")
        return FamiliarTracks(
            collection=(Track(id=2, title="No Surprises"),),
            wave=(Track(id=3, title="Lucky"),),
        )

    async def album_with_tracks(self, album_id: int):
        if self.fail:
            raise RuntimeError("boom")
        if album_id == 404:
            return None
        return Album(id=album_id, title="OK Computer")

    async def track_artists(self, track_id: int):
        if self.fail:
            raise RuntimeError("boom")
        return (Artist(name="Radiohead", id=36800),)

    async def artists_by_ids(self, artist_ids):
        if self.fail:
            raise RuntimeError("boom")
        return tuple(
            Artist(name=f"Artist {aid}", id=aid, cover=Cover(f"cdn.example/{aid}/%%"))
            for aid in artist_ids
        )

    async def resolve_artists(self, title: str, artist: str):
        if self.fail:
            raise RuntimeError("boom")
        return (Artist(name=artist or "Radiohead", id=36800),)

    async def search_artists(self, query: str, limit: int = 6):
        if self.fail:
            raise RuntimeError("boom")
        return (Artist(name="Radiohead", id=36800),)


async def test_library_service_artist_album_familiar_and_resolve_methods():
    svc = LibraryService(_ArtistAlbumCatalog())
    detail = await svc.artist(36800)
    assert detail.name == "Radiohead"
    assert detail.familiar_total == 3

    page = await svc.artist_tracks(36800, page=1, page_size=25)
    assert page.page == 1
    assert page.page_size == 25

    familiar = await svc.artist_familiar(36800)
    assert [t.id for t in familiar.collection] == [2]
    assert [t.id for t in familiar.wave] == [3]
    assert familiar.total == 2

    album = await svc.album(101)
    assert album.title == "OK Computer"

    artists = await svc.track_artists(10)
    assert artists[0].id == 36800

    by_ids = await svc.artists_by_ids([36800, 1020])
    assert [a.id for a in by_ids] == [36800, 1020]
    assert await svc.artists_by_ids([]) == ()

    resolved = await svc.resolve_artists("Creep", "Radiohead")
    assert resolved[0].id == 36800

    found = await svc.search_artists("radio")
    assert found is not None and found[0].id == 36800


async def test_library_service_404_503_and_500_errors():
    svc = LibraryService(_ArtistAlbumCatalog())
    with pytest.raises(RemoteError) as artist_404:
        await svc.artist(404)
    assert artist_404.value.status_code == 404
    assert artist_404.value.message == ARTIST_NOT_FOUND

    with pytest.raises(RemoteError) as album_404:
        await svc.album(404)
    assert album_404.value.status_code == 404
    assert album_404.value.message == ALBUM_NOT_FOUND

    unready = LibraryService(_ArtistAlbumCatalog(ready=False))
    with pytest.raises(RemoteError) as not_ready:
        await unready.artist(1)
    assert not_ready.value.status_code == 503
    assert not_ready.value.message == API_NOT_READY
    assert await unready.search_artists("radio") is None

    broken = LibraryService(_ArtistAlbumCatalog(fail=True))
    with pytest.raises(RemoteError) as failed:
        await broken.artist_familiar(1)
    assert failed.value.status_code == 500
    assert failed.value.message == LIBRARY_FAILED
    assert await broken.search_artists("radio") is None
