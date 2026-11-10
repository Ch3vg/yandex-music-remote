from ym_remote.models.music import Cover, Playlist, Track
from ym_remote.services.library import LibraryService, full_likes_count


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
