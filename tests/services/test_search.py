from ym_remote.cdp.search import SearchHit, tracks_from_search
from ym_remote.models.music import Artist, Track
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
