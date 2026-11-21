import { useEffect, useState } from 'react';
import { fetchJson } from '../api/http';
import type { ArtistCard, CatalogTrack, PromoCard, SearchResponse } from '../api/types';
import { send } from '../api/ws';
import { useRole } from '../store/role';
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

function waveImageSrc(url: string | null | undefined): string | null {
  if (!url) return null;
  const raw = url.trim();
  if (!raw || /^blob:/i.test(raw)) return null;
  if (/^data:image\//i.test(raw)) return raw.length <= 24000 ? raw : null;
  return normalizeCoverUrl(raw, '200x200');
}

function WaveCover({ url }: { url: string | null | undefined }) {
  const src = waveImageSrc(url);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [src]);
  if (!src || failed) return <span className="search-wave-cover ph" aria-hidden="true" />;
  return <img className="search-wave-cover" src={src} alt="" onError={() => setFailed(true)} />;
}

function waveRowProps(card: PromoCard): { className: string; style?: { background: string } } {
  if (!card.cover_url && card.background) {
    return { className: 'search-wave-row has-fill', style: { background: card.background } };
  }
  return { className: 'search-wave-row' };
}

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
  const [waves, setWaves] = useState<PromoCard[]>([]);
  const [lumen, setLumen] = useState<PromoCard | null>(null);
  const admin = useRole() === 'admin';

  const run = () => {
    const q = query.trim();
    if (!q) return;
    setStatus('loading');
    fetchJson<SearchResponse | CatalogTrack[]>(`/api/search?q=${encodeURIComponent(q)}`, 'Ошибка поиска')
      .then((body) => {
        if (Array.isArray(body)) {
          setArtists([]);
          setTracks(body);
          setWaves([]);
          setLumen(null);
        } else {
          setArtists(Array.isArray(body?.artists) ? body.artists : []);
          setTracks(Array.isArray(body?.tracks) ? body.tracks : []);
          setWaves((body?.waves || []).filter((item) => item && item.title && item.title.trim().toLowerCase() !== 'моя волна'));
          setLumen(body?.lumen && body.lumen.title ? body.lumen : null);
        }
        setStatus('done');
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Ошибка поиска');
        setStatus('error');
      });
  };

  const nothingFound = status === 'done' && artists.length === 0 && tracks.length === 0 && waves.length === 0 && !lumen;
  const showPromos = admin && status === 'done' && (waves.length > 0 || lumen);

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

      {showPromos ? (
        <ul className="search-wave-list" id="searchWaves">
          {lumen ? (
            <li>
              <button
                type="button"
                id="btnSearchLumen"
                {...waveRowProps(lumen)}
                onClick={() => {
                  const prompt = (lumen.title || query).trim().slice(0, 300);
                  if (!prompt) return;
                  send({ command: 'start_wave', source: 'lumen', prompt });
                }}
              >
                <WaveCover url={lumen.cover_url} />
                <span className="search-wave-copy">
                  <span className="search-wave-title">{lumen.title}</span>
                  {lumen.subtitle ? <span className="search-wave-sub">{lumen.subtitle}</span> : null}
                </span>
              </button>
            </li>
          ) : null}
          {waves.map((wave, index) => (
            <li key={`${wave.title}-${index}`}>
              <button
                type="button"
                {...waveRowProps(wave)}
                onClick={() => send({
                  command: 'start_wave',
                  source: 'personal',
                  card_title: wave.title,
                  card_index: index,
                })}
              >
                <WaveCover url={wave.cover_url} />
                <span className="search-wave-copy">
                  <span className="search-wave-title">{wave.title}</span>
                  {wave.subtitle ? <span className="search-wave-sub">{wave.subtitle}</span> : null}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

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
