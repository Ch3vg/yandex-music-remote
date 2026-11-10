import { useEffect, useState } from 'react';
import { fetchJson } from '../api/http';
import type { ArtistCard, CatalogTrack, SearchResponse } from '../api/types';
import { TrackRow } from '../components/TrackRow';
import { normalizeCoverUrl } from '../lib/coverUrl';
import './Search.css';

type Props = {
  active: boolean;
  fromHome: boolean;
  onBack: () => void;
  onOpenArtist: (artistId: number, name: string) => void;
  onPlay: (track: CatalogTrack) => void;
  onMenu: (track: CatalogTrack) => void;
};

function ArtistAvatar({ url }: { url: string | null }) {
  const src = normalizeCoverUrl(url, '200x200');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  if (!src || failed) {
    return (
      <span className="search-artist-avatar ph" aria-hidden="true">
        ♪
      </span>
    );
  }

  return (
    <img
      className="search-artist-avatar"
      src={src}
      alt=""
      width={48}
      height={48}
      onError={() => setFailed(true)}
    />
  );
}

export function Search({ active, fromHome, onBack, onOpenArtist, onPlay, onMenu }: Props) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [error, setError] = useState('');
  const [artists, setArtists] = useState<ArtistCard[]>([]);
  const [tracks, setTracks] = useState<CatalogTrack[]>([]);

  const run = () => {
    const q = query.trim();
    if (!q) return;
    setStatus('loading');
    fetchJson<SearchResponse | CatalogTrack[]>(`/api/search?q=${encodeURIComponent(q)}`, 'Ошибка поиска')
      .then((body) => {
        if (Array.isArray(body)) {
          setArtists([]);
          setTracks(body);
        } else {
          setArtists(Array.isArray(body?.artists) ? body.artists : []);
          setTracks(Array.isArray(body?.tracks) ? body.tracks : []);
        }
        setStatus('done');
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Ошибка поиска');
        setStatus('error');
      });
  };

  const nothingFound = status === 'done' && artists.length === 0 && tracks.length === 0;

  return (
    <section className={active ? 'screen active' : 'screen'} id="screenSearch">
      <div className="screen-header">
        {fromHome ? (
          <button type="button" className="nav-btn" id="btnSearchBack" aria-label="Назад" onClick={onBack}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M15 18l-6-6 6-6" />
            </svg>
          </button>
        ) : (
          <span className="header-balance" />
        )}
        <h1 className="screen-title">Поиск</h1>
        <span className="header-balance" />
      </div>
      <div className="search-bar">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-3-3" />
        </svg>
        <input
          id="query"
          placeholder="Трек, альбом, исполнитель"
          autoComplete="off"
          enterKeyHint="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') run();
          }}
        />
      </div>

      {status === 'loading' ? <p className="list-meta">Ищем в приложении…</p> : null}
      {status === 'error' ? <p className="list-meta">{error}</p> : null}
      {nothingFound ? <p className="list-meta">Ничего не найдено</p> : null}

      {status === 'done' && artists.length > 0 ? (
        <div className="search-section">
          <h2 className="search-section-title">Исполнители</h2>
          <ul className="search-artist-list" id="searchArtists">
            {artists.map((artist) => (
              <li key={artist.id}>
                <button
                  type="button"
                  className="search-artist-row"
                  onClick={() => onOpenArtist(artist.id, artist.name)}
                >
                  <ArtistAvatar url={artist.cover_url_hq || artist.cover_url} />
                  <span className="search-artist-name">{artist.name}</span>
                  <span className="search-artist-chev" aria-hidden="true">›</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {status === 'done' && tracks.length > 0 ? (
        <div className="search-section">
          {artists.length > 0 ? <h2 className="search-section-title">Треки</h2> : null}
          <ul className="track-list results" id="results">
            {tracks.map((track, index) => (
              <TrackRow key={`${track.id}-${index}`} track={track} variant="list" onPlay={onPlay} onMenu={onMenu} />
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
