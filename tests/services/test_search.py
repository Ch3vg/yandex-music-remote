from ym_remote.cdp.search import SearchHit, promos_from_markup, tracks_from_search
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
    assert hit.waves == () and hit.lumen is None


def test_promos_from_markup_keeps_lumen_and_separate_wave_cards():
    markup = """
    <div class="results">
      <div data-test-id="TAB">Моя волна</div>
      <div>
        <div data-test-id="QUERY_TO_VIBE_BLOCK">
          <img src="lumen.png"/>
          <div data-test-id="ENTITY_CARD_ENTITY_META">
            <span data-test-id="ENTITY_CARD_ENTITY_META_TITLE">Jdm phonk wav</span>
            <span data-test-id="ENTITY_CARD_ENTITY_META_DESCRIPTION">Я так чувствую — Моя волна от люмена</span>
          </div>
        </div>
        <div data-test-id="SEARCH_VIBE_CARD">
          <img src="a.png"/>
          <span data-test-id="ENTITY_CARD_ENTITY_META_TITLE">Этника сальвадорских улиц</span>
          <span data-test-id="ENTITY_CARD_ENTITY_META_DESCRIPTION">Моя волна</span>
        </div>
        <div data-test-id="SEARCH_VIBE_CARD">
          <span data-test-id="ENTITY_CARD_ENTITY_META_TITLE">Мистический йойк и дыхание севера</span>
          <span data-test-id="ENTITY_CARD_ENTITY_META_DESCRIPTION">Моя волна</span>
        </div>
        <div data-test-id="SEARCH_VIBE_CARD">
          <span data-test-id="ENTITY_CARD_ENTITY_META_TITLE">Читать Лавкрафта под жуткий данжен-синт</span>
          <span data-test-id="ENTITY_CARD_ENTITY_META_DESCRIPTION">Моя волна</span>
        </div>
      </div>
    </div>
    """
    waves, lumen = promos_from_markup(markup)
    assert lumen is not None
    assert lumen.title == "Jdm phonk wav"
    assert lumen.subtitle == "Я так чувствую — Моя волна от люмена"
    assert lumen.cover_url == "lumen.png"
    assert [item.title for item in waves] == [
        "Этника сальвадорских улиц",
        "Мистический йойк и дыхание севера",
        "Читать Лавкрафта под жуткий данжен-синт",
    ]
    assert [item.subtitle for item in waves] == ["Моя волна", "Моя волна", "Моя волна"]


def test_tracks_from_search_drops_generic_wave_title():
    hit = tracks_from_search(
        {
            "ok": True,
            "tracks": [],
            "waves": [
                {"title": "Моя волна", "subtitle": "Моя волна"},
                {"title": "Этника сальвадорских улиц", "subtitle": "Моя волнаМистический йойк Моя волна"},
                {"title": "Этника сальвадорских улиц", "subtitle": "Моя волна"},
            ],
        }
    )
    assert [item.title for item in hit.waves] == ["Этника сальвадорских улиц"]
    assert hit.waves[0].subtitle == "Моя волна"


def test_tracks_from_search_keeps_waves_and_lumen():
    hit = tracks_from_search(
        {
            "ok": True,
            "tracks": [],
            "waves": [
                {"title": "Энергичное", "subtitle": "Моя волна по настроению", "cover": "cdn/w"},
                {"title": "Бодрое утро", "subtitle": "Моя волна", "cover": ""},
            ],
            "lumen": {"title": "JDM phonk", "subtitle": "Моя волна от люмена", "cover": "cdn/l"},
        }
    )
    assert [item.title for item in hit.waves] == ["Энергичное", "Бодрое утро"]
    assert hit.waves[0].cover_url == "cdn/w"
    assert hit.lumen is not None and hit.lumen.title == "JDM phonk"
    assert hit.lumen.cover_url == "cdn/l"


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
