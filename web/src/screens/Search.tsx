import { useState } from 'react';
import type { CatalogTrack } from '../api/types';
import { fetchJson } from '../api/http';
import { TrackRow } from '../components/TrackRow';
import './Search.css';

type Props = {
  active: boolean;
  fromHome: boolean;
  onBack: () => void;
  onPlay: (track: CatalogTrack) => void;
  onMenu: (track: CatalogTrack) => void;
};

export function Search({ active, fromHome, onBack, onPlay, onMenu }: Props) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [error, setError] = useState('');
  const [tracks, setTracks] = useState<CatalogTrack[]>([]);

  const run = () => {
    const q = query.trim();
    if (!q) return;
    setStatus('loading');
    fetchJson<CatalogTrack[]>(`/search?q=${encodeURIComponent(q)}`, 'Ошибка поиска')
      .then((body) => {
        setTracks(Array.isArray(body) ? body : []);
        setStatus('done');
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Ошибка поиска');
        setStatus('error');
      });
  };

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
      <ul className="track-list results" id="results">
        {status === 'loading' ? <li className="list-meta">Ищем в приложении…</li> : null}
        {status === 'error' ? <li className="list-meta">{error}</li> : null}
        {status === 'done' && tracks.length === 0 ? <li className="list-meta">Ничего не найдено</li> : null}
        {status === 'done'
          ? tracks.map((track, index) => (
              <TrackRow key={`${track.id}-${index}`} track={track} variant="list" onPlay={onPlay} onMenu={onMenu} />
            ))
          : null}
      </ul>
    </section>
  );
}
