import { useEffect, useRef, useState } from 'react';
import { fetchJson } from '../api/http';
import type {
  ArtistFamiliarResponse,
  ArtistTracksPage,
  CatalogTrack,
  PlayContext,
} from '../api/types';
import type { ArtistTracksMode } from '../app/screen';
import { TrackRow } from '../components/TrackRow';
import './ArtistTracks.css';

export type ArtistTracksRouteRequest = {
  artistId: number;
  artistName: string;
  mode: ArtistTracksMode;
  nonce: number;
};

type FamiliarTab = 'collection' | 'wave';

type Props = {
  active: boolean;
  request: ArtistTracksRouteRequest | null;
  onBack: () => void;
  onPlay: (track: CatalogTrack, context: PlayContext) => void;
  onMenu: (track: CatalogTrack, context: PlayContext) => void;
};

const PAGE_SIZE = 50;

export function ArtistTracks({ active, request, onBack, onPlay, onMenu }: Props) {
  const [filter, setFilter] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [tracks, setTracks] = useState<CatalogTrack[]>([]);
  const [collectionTracks, setCollectionTracks] = useState<CatalogTrack[]>([]);
  const [waveTracks, setWaveTracks] = useState<CatalogTrack[]>([]);
  const [familiarTab, setFamiliarTab] = useState<FamiliarTab>('collection');
  const [familiarHasSplit, setFamiliarHasSplit] = useState(true);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [error, setError] = useState('');
  const [retrySeq, setRetrySeq] = useState(0);

  const listRef = useRef<HTMLUListElement>(null);
  const filterInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setFilter('');
    setSearchOpen(request?.mode !== 'familiar');
    if (!request) return;
    let cancel = false;
    setStatus('loading');
    setTracks([]);
    setCollectionTracks([]);
    setWaveTracks([]);
    setFamiliarTab('collection');
    setFamiliarHasSplit(true);
    setPage(0);
    setHasMore(false);
    setLoadingMore(false);
    setError('');
    if (listRef.current) listRef.current.scrollTop = 0;

    if (request.mode === 'familiar') {
      fetchJson<ArtistFamiliarResponse>(
        `/api/library/artist/${request.artistId}/familiar`,
        'Не удалось загрузить треки исполнителя',
      )
        .then((body) => {
          if (cancel) return;
          const hasSplit = Array.isArray(body.collection_tracks) || Array.isArray(body.wave_tracks);
          const rawCollection = hasSplit ? (body.collection_tracks ?? []) : (body.tracks ?? []);
          const rawWave = hasSplit ? (body.wave_tracks ?? []) : [];
          const nextCollection = rawCollection.map((track, idx) => ({
            ...track,
            playlist_index: track.playlist_index ?? idx,
          }));
          const nextWave = rawWave.map((track, idx) => ({
            ...track,
            playlist_index: track.playlist_index ?? idx,
          }));
          setFamiliarHasSplit(hasSplit);
          setCollectionTracks(nextCollection);
          setWaveTracks(nextWave);
          setFamiliarTab(nextCollection.length > 0 || nextWave.length === 0 ? 'collection' : 'wave');
          setHasMore(false);
          setStatus('ready');
        })
        .catch((reason: unknown) => {
          if (cancel) return;
          setError(reason instanceof Error ? reason.message : 'Не удалось загрузить треки исполнителя');
          setStatus('error');
        });
    } else {
      fetchJson<ArtistTracksPage>(
        `/api/library/artist/${request.artistId}/tracks?page=0&page_size=${PAGE_SIZE}`,
        'Не удалось загрузить треки исполнителя',
      )
        .then((body) => {
          if (cancel) return;
          const list = (body.tracks ?? []).map((track, idx) => ({
            ...track,
            playlist_index: track.playlist_index ?? idx,
          }));
          setTracks(list);
          setPage(body.page ?? 0);
          setHasMore(body.has_more === true);
          setStatus('ready');
        })
        .catch((reason: unknown) => {
          if (cancel) return;
          setError(reason instanceof Error ? reason.message : 'Не удалось загрузить треки исполнителя');
          setStatus('error');
        });
    }

    return () => {
      cancel = true;
    };
  }, [request?.artistId, request?.mode, request?.nonce, retrySeq]);

  const selectFamiliarTab = (tab: FamiliarTab) => {
    setFamiliarTab(tab);
    if (listRef.current) {
      listRef.current.scrollTop = 0;
    }
  };

  const toggleSearch = () => {
    setSearchOpen((prev) => {
      const next = !prev;
      if (next) {
        window.requestAnimationFrame(() => filterInputRef.current?.focus());
      } else {
        setFilter('');
      }
      return next;
    });
  };

  const loadMore = () => {
    if (!request || request.mode !== 'all' || loadingMore || !hasMore) return;
    const nextPage = page + 1;
    setLoadingMore(true);
    fetchJson<ArtistTracksPage>(
      `/api/library/artist/${request.artistId}/tracks?page=${nextPage}&page_size=${PAGE_SIZE}`,
      'Не удалось подгрузить треки',
    )
      .then((body) => {
        setTracks((prev) => {
          const offset = prev.length;
          const appended = (body.tracks ?? []).map((track, idx) => ({
            ...track,
            playlist_index: offset + idx,
          }));
          return [...prev, ...appended];
        });
        setPage(body.page ?? nextPage);
        setHasMore(body.has_more === true);
      })
      .catch(() => {
        // Toast or retry remains available via button
      })
      .finally(() => {
        setLoadingMore(false);
      });
  };

  const artistId = request?.artistId ?? 0;
  const mode = request?.mode ?? 'all';
  const isFamiliar = mode === 'familiar';

  const activeContext: PlayContext = isFamiliar
    ? {
        artist_id: artistId,
        artist_mode: !familiarHasSplit
          ? 'familiar'
          : familiarTab === 'wave'
            ? 'familiar_wave'
            : 'familiar_collection',
      }
    : {
        artist_id: artistId,
        artist_mode: 'tracks',
      };

  const subtitle = (request?.artistName || '').trim();
  const allHeading = subtitle ? `Треки · ${subtitle}` : 'Треки';
  const query = filter.trim().toLowerCase();
  const matchesQuery = (track: CatalogTrack) =>
    !query || `${track.title} ${track.artist}`.toLowerCase().includes(query);

  const activeFamiliarSource = familiarTab === 'wave' ? waveTracks : collectionTracks;
  const visibleTracks = (isFamiliar ? activeFamiliarSource : tracks).filter(matchesQuery);
  const hasAnyFamiliarTracks = collectionTracks.length > 0 || waveTracks.length > 0;
  const showSearchInput = !isFamiliar || searchOpen;

  const emptyMessage =
    isFamiliar && !query && hasAnyFamiliarTracks && activeFamiliarSource.length === 0
      ? familiarTab === 'collection'
        ? 'Нет лайкнутых треков в Коллекции'
        : 'Нет прослушанных треков в Моей волне'
      : 'Ничего не найдено';

  return (
    <section className={active ? 'screen active' : 'screen'} id="screenArtistTracks">
      {isFamiliar ? (
        <div className="artist-familiar-top">
          <div className="artist-familiar-nav">
            <button
              type="button"
              className="nav-btn artist-familiar-back"
              id="btnArtistTracksBack"
              aria-label="Назад"
              onClick={onBack}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 12H5" />
                <path d="M12 19l-7-7 7-7" />
              </svg>
            </button>
            {status === 'ready' && hasAnyFamiliarTracks ? (
              <button
                type="button"
                className={searchOpen ? 'nav-btn artist-familiar-search-toggle active' : 'nav-btn artist-familiar-search-toggle'}
                id="btnFamiliarSearchToggle"
                aria-label="Поиск в треках"
                aria-expanded={searchOpen}
                onClick={toggleSearch}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="7" />
                  <path d="M20 20l-3.5-3.5" />
                </svg>
              </button>
            ) : null}
          </div>

          <h1 className="artist-familiar-heading" id="artistTracksTitle">Знакомое вам</h1>

          <div className="artist-familiar-tabs" role="tablist" aria-label="Разделы знакомых треков">
            <button
              type="button"
              role="tab"
              id="tabFamiliarCollection"
              aria-selected={familiarTab === 'collection'}
              className={familiarTab === 'collection' ? 'artist-familiar-tab active' : 'artist-familiar-tab'}
              onClick={() => selectFamiliarTab('collection')}
            >
              У вас в Коллекции
            </button>
            <button
              type="button"
              role="tab"
              id="tabFamiliarWave"
              aria-selected={familiarTab === 'wave'}
              className={familiarTab === 'wave' ? 'artist-familiar-tab active' : 'artist-familiar-tab'}
              onClick={() => selectFamiliarTab('wave')}
            >
              Слушали в Моей волне
            </button>
          </div>
        </div>
      ) : (
        <div className="artist-tracks-header">
          <button type="button" className="nav-btn" id="btnArtistTracksBack" aria-label="Назад" onClick={onBack}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5" />
              <path d="M12 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="artist-tracks-titles">
            <h1 id="artistTracksTitle">{allHeading}</h1>
          </div>
        </div>
      )}

      {showSearchInput ? (
        <div className={isFamiliar ? 'playlist-search artist-familiar-search' : 'playlist-search'}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" opacity="0.45">
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3-3" />
          </svg>
          <input
            ref={filterInputRef}
            type="search"
            id="artistTracksFilter"
            placeholder="Поиск в треках"
            autoComplete="off"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
        </div>
      ) : null}

      <ul className="track-list" id="artistTracksList" ref={listRef}>
        {status === 'loading' ? <li className="list-meta">Загрузка…</li> : null}
        {status === 'error' ? (
          <li className="list-meta artist-tracks-error">
            <div>{error}</div>
            <button type="button" className="artist-tracks-more-btn" onClick={() => setRetrySeq((n) => n + 1)}>
              Повторить
            </button>
          </li>
        ) : null}
        {status === 'ready' && visibleTracks.length === 0 ? (
          <li className="list-meta">{emptyMessage}</li>
        ) : null}
        {status === 'ready'
          ? visibleTracks.map((track, idx) => (
              <TrackRow
                key={`${isFamiliar ? familiarTab : 'all'}-${track.id}-${track.playlist_index ?? idx}`}
                track={track}
                variant="list"
                onPlay={(item) => onPlay(item, activeContext)}
                onMenu={(item) => onMenu(item, activeContext)}
              />
            ))
          : null}
        {status === 'ready' && !isFamiliar && hasMore && !query ? (
          <li className="artist-tracks-more-item">
            <button
              type="button"
              className="artist-tracks-more-btn"
              id="btnArtistTracksMore"
              disabled={loadingMore}
              onClick={loadMore}
            >
              {loadingMore ? 'Загрузка…' : 'Показать ещё'}
            </button>
          </li>
        ) : null}
      </ul>
    </section>
  );
}
