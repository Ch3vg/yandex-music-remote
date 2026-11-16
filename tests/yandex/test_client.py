from __future__ import annotations

from types import SimpleNamespace

from ym_remote.yandex.client import YandexLibrary


class NotFoundError(Exception):
    pass


class _FakeRequest:
    def __init__(self, responses: dict[str, object] | None = None):
        self.responses = responses or {}
        self.urls: list[str] = []

    async def get(self, url: str):
        self.urls.append(url)
        return self.responses.get(url)


class _FakeYmClient:
    base_url = "https://api.music.yandex.net"

    def __init__(self):
        self._request = _FakeRequest()
        self.brief_map: dict[int, object] = {}
        self.direct_albums_map: dict[int, object] = {}
        self.skeleton_map: dict[int, object] = {}
        self.artist_tracks_map: dict[tuple[int, int, int], object] = {}
        self.artist_track_ids_map: dict[int, list] = {}
        self.likes_tracks_list: list = []
        self.tracks_db: dict[int | str, object] = {}
        self.albums_map: dict[int, object] = {}
        self.search_map: dict[str, object] = {}
        self.artists_db: dict[int, object] = {}
        self.tracks_calls: list[list] = []

    async def artists(self, artist_ids):
        return [self.artists_db[aid] for aid in artist_ids if aid in self.artists_db]

    async def artists_brief_info(self, artist_id: int):
        val = self.brief_map.get(artist_id)
        if isinstance(val, Exception):
            raise val
        return val

    async def artists_direct_albums(self, artist_id: int, page: int = 0, page_size: int = 30, sort_by: str = "year"):
        return self.direct_albums_map.get(artist_id)

    async def artists_skeleton(self, artist_id: int, skeleton_id: str):
        val = self.skeleton_map.get(artist_id)
        if isinstance(val, Exception):
            raise val
        return val

    async def artists_tracks(self, artist_id: int, page: int = 0, page_size: int = 50):
        val = self.artist_tracks_map.get((artist_id, page, page_size))
        if isinstance(val, Exception):
            raise val
        return val

    async def artists_track_ids(self, artist_id: int, page: int = 0, page_size: int = 300):
        return self.artist_track_ids_map.get(artist_id, [])

    async def users_likes_tracks(self, uid):
        return SimpleNamespace(tracks=self.likes_tracks_list)

    async def tracks(self, ids):
        self.tracks_calls.append(list(ids))
        out = []
        for raw in ids:
            if raw in self.tracks_db:
                out.append(self.tracks_db[raw])
                continue
            head = int(str(raw).split(":")[0])
            if head in self.tracks_db:
                out.append(self.tracks_db[head])
        return out

    async def albums_with_tracks(self, album_id: int):
        val = self.albums_map.get(album_id)
        if isinstance(val, Exception):
            raise val
        return val

    async def search(self, query: str, type_: str = "all"):
        return self.search_map.get(query)


def _make_library(fake_client: _FakeYmClient) -> YandexLibrary:
    lib = YandexLibrary("test-token")
    lib._client = fake_client
    lib.ready = True
    lib.uid = 42
    return lib


async def test_artist_detail_splits_albums_and_singles_and_uses_skeleton_familiar_count():
    client = _FakeYmClient()
    client.brief_map[36800] = SimpleNamespace(
        artist=SimpleNamespace(
            id=36800,
            name="Radiohead",
            cover=None,
            derived_colors={"average": "#5bbdd6", "accent": "#33d6ff"},
            counts={"tracks": 140, "direct_albums": 3},
        ),
        all_covers=[{"uri": "avatars.yandex.net/rh/%%"}],
        popular_tracks=[
            {
                "id": 10,
                "title": "Creep",
                "artists": [{"id": 36800, "name": "Radiohead"}],
                "albums": [{"id": 100, "title": "Pablo Honey"}],
            },
            {
                "id": 11,
                "title": "Karma Police",
                "artists": [{"id": 36800, "name": "Radiohead"}],
                "albums": [{"id": 101, "title": "OK Computer"}],
            },
        ],
        albums=[],
    )
    client.direct_albums_map[36800] = SimpleNamespace(
        albums=[
            {"id": 101, "title": "OK Computer", "year": 1997, "type": None, "track_count": 12},
            {"id": 102, "title": "No Surprises", "year": 1998, "type": "single", "track_count": 3},
            {"id": 101, "title": "Duplicate", "year": 1997},
        ]
    )
    client.skeleton_map[36800] = {
        "blocks": [
            {
                "type": "TABS",
                "data": {
                    "tabs": [
                        {
                            "blocks": [
                                {
                                    "type": "FAMILIAR_YOU",
                                    "data": {"source": {"uri": "/artists/36800/familiar-you"}},
                                }
                            ]
                        }
                    ]
                },
            }
        ]
    }
    client.likes_tracks_list = [SimpleNamespace(id=11, album_id=101)]
    client._request.responses["https://api.music.yandex.net/artists/36800/familiar-you"] = {
        "tracks": ["10:100", "11:101", "12:101"]
    }
    client.tracks_db = {
        10: {"id": 10, "title": "Creep", "artists": [{"id": 36800, "name": "Radiohead"}]},
        11: {"id": 11, "title": "Karma Police", "artists": [{"id": 36800, "name": "Radiohead"}]},
        12: {"id": 12, "title": "Paranoid Android", "artists": [{"id": 36800, "name": "Radiohead"}]},
    }

    lib = _make_library(client)
    detail = await lib.artist_detail(36800)

    assert detail is not None
    assert detail.id == 36800
    assert detail.name == "Radiohead"
    assert detail.cover is not None
    assert detail.cover.hq_url() == "https://avatars.yandex.net/rh/1000x1000"
    assert detail.ambient_color == "#5bbdd6"
    assert detail.total_tracks == 140
    assert detail.total_albums == 3
    assert detail.familiar_total == 3
    assert [t.id for t in detail.popular_tracks] == [10, 11]
    assert [t.playlist_index for t in detail.popular_tracks] == [0, 1]
    assert [a.id for a in detail.albums] == [101]
    assert detail.albums[0].artist_line() == "Radiohead"
    assert [s.id for s in detail.singles] == [102]
    assert detail.singles[0].album_type == "single"

    urls_after_detail = len(client._request.urls)
    split_familiar = await lib.artist_familiar(36800)
    assert [t.id for t in split_familiar.collection] == [11]
    assert [t.playlist_index for t in split_familiar.collection] == [0]
    assert [t.id for t in split_familiar.wave] == [10, 12]
    assert [t.playlist_index for t in split_familiar.wave] == [0, 1]
    assert split_familiar.total == 3
    assert len(client._request.urls) == urls_after_detail

    familiar = await lib.artist_familiar_tracks(36800)
    assert [t.id for t in familiar] == [11, 10, 12]
    assert [t.album_id() for t in familiar] == [101, 100, 101]
    assert [t.playlist_index for t in familiar] == [0, 1, 2]
    assert len(client.tracks_calls) == 1


async def test_artist_familiar_preserves_full_wave_list_and_unique_familiar_total():
    client = _FakeYmClient()
    client.brief_map[17129344] = SimpleNamespace(
        artist=SimpleNamespace(
            id=17129344,
            name="навздохе",
            cover=None,
            counts={"tracks": 25, "direct_albums": 1},
        ),
        all_covers=[],
        popular_tracks=[],
        albums=[],
    )
    direct_url = (
        "https://api.music.yandex.net/artists/17129344/familiar-you"
        "?waveTracksLimit=200&collectionTracksLimit=200"
    )
    client._request.responses[direct_url] = {
        "collection": {
            "tracks": [
                {
                    "id": "101",
                    "title": "В коллекции 1",
                    "artists": [{"id": 17129344, "name": "навздохе"}],
                    "albums": [{"id": 5001, "title": "Single 1"}],
                },
                {
                    "id": "102",
                    "title": "В коллекции 2",
                    "artists": [{"id": 17129344, "name": "навздохе"}],
                    "albums": [{"id": 5002, "title": "Single 2"}],
                },
            ]
        },
        "wave": {
            "tracks": [
                {
                    "id": "101",
                    "title": "В коллекции 1",
                    "artists": [{"id": 17129344, "name": "навздохе"}],
                    "albums": [{"id": 5001, "title": "Single 1"}],
                },
                {
                    "id": "201",
                    "title": "Из Моей волны 1",
                    "artists": [{"id": 17129344, "name": "навздохе"}],
                    "albums": [{"id": 5003, "title": "Wave EP"}],
                },
                {
                    "id": "202",
                    "title": "Из Моей волны 2",
                    "artists": [{"id": 17129344, "name": "навздохе"}],
                    "albums": [{"id": 5004, "title": "Wave Single"}],
                },
            ]
        },
    }

    lib = _make_library(client)
    detail = await lib.artist_detail(17129344)
    assert detail is not None
    # Unique union across collection {101, 102} and wave {101, 201, 202} = 4
    assert detail.familiar_total == 4

    familiar = await lib.artist_familiar(17129344)
    assert [t.id for t in familiar.collection] == [101, 102]
    assert [t.playlist_index for t in familiar.collection] == [0, 1]
    # Wave tab preserves full wave.tracks order (0..2) matching desktop tab=vibe
    assert [t.id for t in familiar.wave] == [101, 201, 202]
    assert [t.playlist_index for t in familiar.wave] == [0, 1, 2]
    assert familiar.total == 4
    assert [t.id for t in familiar.all_tracks()] == [101, 102, 201, 202]
    assert client.tracks_calls == []
    assert client._request.urls == [direct_url]


async def test_artist_familiar_falls_back_to_user_likes_when_skeleton_missing():
    client = _FakeYmClient()
    client.skeleton_map[500] = {
        "blocks": [
            {
                "type": "FAMILIAR_YOU",
                "data": {"source": {"uri": "/artists/500/familiar-you/info?withWaveInfo=true"}},
            }
        ]
    }
    client._request.responses[
        "https://api.music.yandex.net/artists/500/familiar-you?waveTracksLimit=200&collectionTracksLimit=200"
    ] = {}
    client.likes_tracks_list = [
        SimpleNamespace(id=202, album_id=88),
        SimpleNamespace(id=999, album_id=77),
        SimpleNamespace(id="201:85", album_id=None),
    ]
    client.artist_track_ids_map[500] = ["201:85", "202:88", "203:90"]
    client.tracks_db = {
        201: {"id": 201, "title": "First Song", "artists": [{"id": 500, "name": "Band"}]},
        202: {"id": 202, "title": "Liked Latest", "artists": [{"id": 500, "name": "Band"}]},
    }

    lib = _make_library(client)
    split = await lib.artist_familiar(500)
    assert [t.id for t in split.collection] == [202, 201]
    assert split.wave == ()

    familiar = await lib.artist_familiar_tracks(500)

    # Preserves order in user's likes collection: 202 first, then 201
    assert [t.id for t in familiar] == [202, 201]
    assert [t.album_id() for t in familiar] == [88, 85]
    assert [t.playlist_index for t in familiar] == [0, 1]


async def test_artist_detail_and_album_return_none_on_not_found():
    client = _FakeYmClient()
    client.brief_map[404] = NotFoundError("not found")
    client.albums_map[404] = NotFoundError("not found")
    client.albums_map[77] = {
        "id": 77,
        "title": "OK Computer",
        "year": 1997,
        "artists": [{"id": 36800, "name": "Radiohead"}],
        "volumes": [[{"id": 11, "title": "Airbag"}]],
    }

    lib = _make_library(client)
    assert await lib.artist_detail(404) is None
    assert await lib.album_with_tracks(404) is None

    album = await lib.album_with_tracks(77)
    assert album is not None
    assert album.id == 77
    assert [t.id for t in album.tracks] == [11]
    assert album.tracks[0].album_id() == 77


async def test_artist_tracks_pagination_and_not_found():
    client = _FakeYmClient()
    client.artist_tracks_map[(36800, 1, 2)] = SimpleNamespace(
        tracks=[
            {"id": 21, "title": "T3", "albums": [{"id": 1}]},
            {"id": 22, "title": "T4", "albums": [{"id": 1}]},
        ],
        pager={"total": 5},
    )
    client.artist_tracks_map[(404, 0, 50)] = NotFoundError("not found")

    lib = _make_library(client)
    page = await lib.artist_tracks(36800, page=1, page_size=2)
    assert page.page == 1
    assert page.page_size == 2
    assert page.total == 5
    assert page.has_more is True
    assert [t.id for t in page.tracks] == [21, 22]
    assert [t.playlist_index for t in page.tracks] == [2, 3]

    empty = await lib.artist_tracks(404)
    assert empty.tracks == ()
    assert empty.has_more is False


async def test_search_artists_and_resolve_artists():
    client = _FakeYmClient()
    client.search_map["кино"] = SimpleNamespace(
        best={"type": "artist", "result": {"id": 41052, "name": "Кино", "og_image": "cdn/kino/%%"}},
        artists={
            "results": [
                {"id": 41052, "name": "Кино"},
                {"id": 50000, "name": "Кинопробы"},
            ]
        },
    )
    client.search_map["Soltwine, Драгни Заблудись"] = SimpleNamespace(
        best=None,
        tracks={
            "results": [
                {
                    "id": 8,
                    "title": "Заблудись",
                    "artists": [
                        {"id": 101, "name": "Soltwine", "cover": {"uri": "cdn/soltwine/%%"}},
                        {"id": 102, "name": "Драгни", "og_image": "cdn/dragni/%%"},
                    ],
                }
            ]
        },
    )
    client.search_map["Soltwine"] = SimpleNamespace(
        best={"type": "artist", "result": {"id": 101, "name": "Soltwine", "cover": {"uri": "cdn/soltwine/%%"}}},
        artists={"results": []},
    )
    client.search_map["Драгни"] = SimpleNamespace(
        best={"type": "artist", "result": {"id": 102, "name": "Драгни", "og_image": "cdn/dragni/%%"}},
        artists={"results": []},
    )
    client.tracks_db[8] = {
        "id": 8,
        "title": "Заблудись",
        "artists": [
            {"id": 101, "name": "Soltwine", "cover": {"uri": "cdn/soltwine/%%"}},
            {"id": 102, "name": "Драгни", "og_image": "cdn/dragni/%%"},
        ],
    }

    lib = _make_library(client)

    found = await lib.search_artists("кино", limit=6)
    assert [(a.id, a.name) for a in found] == [(41052, "Кино"), (50000, "Кинопробы")]
    assert found[0].cover is not None

    by_track = await lib.resolve_artists("Заблудись", "Soltwine, Драгни")
    assert [(a.id, a.name) for a in by_track] == [(101, "Soltwine"), (102, "Драгни")]
    assert [a.cover.list_url() if a.cover else None for a in by_track] == [
        "https://cdn/soltwine/200x200",
        "https://cdn/dragni/200x200",
    ]

    by_split = await lib.resolve_artists("Unknown Song", "Soltwine, Драгни")
    assert [(a.id, a.name) for a in by_split] == [(101, "Soltwine"), (102, "Драгни")]
    assert [a.cover.list_url() if a.cover else None for a in by_split] == [
        "https://cdn/soltwine/200x200",
        "https://cdn/dragni/200x200",
    ]

    from_track_id = await lib.track_artists(8)
    assert [(a.id, a.name) for a in from_track_id] == [(101, "Soltwine"), (102, "Драгни")]
    assert [a.cover.list_url() if a.cover else None for a in from_track_id] == [
        "https://cdn/soltwine/200x200",
        "https://cdn/dragni/200x200",
    ]


async def test_artists_by_ids_version_stripping_partial_parts_and_dark_derived_blend():
    client = _FakeYmClient()
    client.artists_db = {
        8095900: {
            "id": 8095900,
            "name": "Три дня дождя",
            "cover": {"uri": "cdn/tdd/%%"},
        },
        6260322: {
            "id": 6260322,
            "name": "МУККА",
            "og_image": "cdn/mukka/%%",
        },
    }
    # Track match only has first artist and lacks cover; version in query is "(Remix)"
    client.search_map["Три дня дождя, МУККА Перезаряжай (Remix)"] = SimpleNamespace(
        best=None,
        tracks={
            "results": [
                {
                    "id": 500,
                    "title": "Перезаряжай",
                    "version": "Remix",
                    "artists": [{"id": 8095900, "name": "Три дня дождя", "cover": None}],
                }
            ]
        },
    )
    client.search_map["МУККА"] = SimpleNamespace(
        best={"type": "artist", "result": {"id": 6260322, "name": "МУККА", "cover": None}},
        artists={"results": []},
    )
    client.brief_map[6129147] = SimpleNamespace(
        artist=SimpleNamespace(
            id=6129147,
            name="вышел покурить",
            cover={"uri": "cdn/vp/%%"},
            derived_colors={"average": "#1e1e1e", "accent": "#999999", "mini_player": "#b7b7b7"},
            counts={"tracks": 10, "direct_albums": 0},
        ),
        all_covers=[],
        popular_tracks=[],
        albums=[],
    )

    lib = _make_library(client)

    batch = await lib.artists_by_ids([6260322, 8095900, 6260322, -1])
    assert [(a.id, a.name) for a in batch] == [(6260322, "МУККА"), (8095900, "Три дня дождя")]
    assert [a.cover.list_url() if a.cover else None for a in batch] == [
        "https://cdn/mukka/200x200",
        "https://cdn/tdd/200x200",
    ]

    resolved = await lib.resolve_artists("Перезаряжай (Remix)", "Три дня дождя, МУККА")
    assert [(a.id, a.name) for a in resolved] == [(8095900, "Три дня дождя"), (6260322, "МУККА")]
    assert [a.cover.list_url() if a.cover else None for a in resolved] == [
        "https://cdn/tdd/200x200",
        "https://cdn/mukka/200x200",
    ]

    dark_detail = await lib.artist_detail(6129147)
    assert dark_detail is not None
    assert dark_detail.ambient_color == "#3e3e3e"
