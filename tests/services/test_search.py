from ym_remote.cdp.search import SearchHit, tracks_from_search
from ym_remote.models.music import Artist, Cover, Track
from ym_remote.services.gate import HeavyGate
from ym_remote.services.search import SearchService


def test_search_payload_keeps_numeric_ids():
    hit = tracks_from_search(
        {
            "ok": True,
            "tracks": [
                {
                    "title": "Заблудись",
                    "artists": ["Soltwine", "Драгни"],
                    "track_id": 8,
                    "album_id": 44,
                    "cover": "",
                }
            ],
        }
    )
    assert hit.tracks[0].id == 8
    assert hit.tracks[0].album_id() == 44
    assert hit.tracks[0].artist_line() == "Soltwine, Драгни"


class Adapter:
    def __init__(self, tracks):
        self.tracks = tracks

    async def search(self, query):
        return SearchHit(self.tracks)


class Albums:
    def __init__(self):
        self.calls = []

    async def album_id_for(self, track_id):
        self.calls.append(track_id)
        return 44


async def test_search_fills_a_missing_album_before_returning_the_row():
    albums = Albums()
    service = SearchService(
        Adapter((Track(id=8, title="Заблудись", artists=(Artist("Soltwine"), Artist("Драгни"))),)),
        HeavyGate(),
        albums,
    )
    tracks = await service.search("Заблудись")
    assert albums.calls == [8]
    assert tracks[0].id == 8
    assert tracks[0].album_id() == 44


def test_tracks_from_search_parses_artist_refs_and_artist_cards():
    hit = tracks_from_search(
        {
            "ok": True,
            "tracks": [
                {
                    "title": "Заблудись",
                    "artists": ["Soltwine", "Драгни"],
                    "artist_refs": [
                        {"id": 101, "name": "Soltwine"},
                        {"id": 102, "name": "Драгни"},
                    ],
                    "track_id": 8,
                    "album_id": 44,
                    "cover": "cdn/t/%%",
                }
            ],
            "artist_cards": [
                {"id": 101, "name": "Soltwine", "cover": "cdn/a/%%"},
                {"id": 101, "name": "Duplicate", "cover": ""},
            ],
        }
    )
    assert [(a.id, a.name) for a in hit.tracks[0].artists] == [
        (101, "Soltwine"),
        (102, "Драгни"),
    ]
    assert [(a.id, a.name) for a in hit.artists] == [(101, "Soltwine")]


async def test_search_all_uses_api_artists_and_falls_back_to_cdp_artists():
    cdp_artists = (Artist(name="CDP Artist", id=77),)
    api_artists = (Artist(name="API Artist", id=88, cover=Cover("cdn/%%")),)

    class FullAdapter:
        async def search(self, query):
            return SearchHit(
                tracks=(Track(id=8, title="Song", artists=(Artist("API Artist", id=88),)),),
                artists=cdp_artists,
            )

    class LibWithArtists:
        def __init__(self, result):
            self.result = result

        async def search_artists(self, query):
            return self.result

        async def album_id_for(self, track_id):
            return 44

    with_api = SearchService(FullAdapter(), HeavyGate(), LibWithArtists(api_artists))
    view_api = await with_api.search_all("API")
    assert view_api.artists == api_artists
    assert view_api.tracks[0].album_id() == 44

    fallback = SearchService(FullAdapter(), HeavyGate(), LibWithArtists(None))
    view_cdp = await fallback.search_all("CDP")
    assert view_cdp.artists == cdp_artists

    empty = await with_api.search_all("   ")
    assert empty.artists == ()
    assert empty.tracks == ()
