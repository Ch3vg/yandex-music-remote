import { useEffect, useState } from 'react';
import type { CatalogTrack, HomeResponse, PlayContext } from '../api/types';
import { fetchJson } from '../api/http';
import { CoverFrame } from '../components/CoverArt';
import { TrackRow } from '../components/TrackRow';
import { normalizeCoverUrl } from '../lib/coverUrl';
import { formatTrackCount } from '../lib/trackCount';
import './Home.css';

type Status = 'loading' | 'ready' | 'error';

type Props = {
  active: boolean;
  connected: boolean;
  statusTitle: string;
  onQr: () => void;
  onSearch: () => void;
  onOpenPlaylist: (kind: number, title: string) => void;
  onPlay: (track: CatalogTrack) => void;
  onMenu: (track: CatalogTrack) => void;
  onLikesContext: (context: PlayContext | null) => void;
};

function LikesArt({ url }: { url: string | null }) {
  const src = normalizeCoverUrl(url);
  const [ok, setOk] = useState(false);
  useEffect(() => {
    setOk(false);
  }, [src]);
  return (
    <div className="likes-hero-art" id="likesHeroArt">
      {ok ? null : (
        <svg className="heart-fallback" viewBox="0 0 24 24" fill="#fff" aria-hidden="true">
          <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
        </svg>
      )}
      {src ? (
        <img
          alt=""
          src={src}
          onLoad={() => setOk(true)}
          onError={() => setOk(false)}
        />
      ) : null}
    </div>
  );
}

export function Home({
  active,
  connected,
  statusTitle,
  onQr,
  onSearch,
  onOpenPlaylist,
  onPlay,
  onMenu,
  onLikesContext,
}: Props) {
  const [status, setStatus] = useState<Status>('loading');
  const [error, setError] = useState('');
  const [title, setTitle] = useState('Мне нравится');
  const [count, setCount] = useState(0);
  const [cover, setCover] = useState<string | null>(null);
  const [kind, setKind] = useState(3);
  const [tracks, setTracks] = useState<CatalogTrack[]>([]);
  const [playlists, setPlaylists] = useState<HomeResponse['playlists']>([]);

  useEffect(() => {
    let cancel = false;
    fetchJson<HomeResponse>('/api/library/home', 'Ошибка загрузки')
      .then((data) => {
        if (cancel) return;
        const likes = data.likes || {};
        const nextKind = likes.kind || 3;
        setKind(nextKind);
        setTitle(likes.title || 'Мне нравится');
        setCount(Number(likes.track_count) || 0);
        setCover(likes.cover_url ?? null);
        const preview = (likes.tracks || []).slice(0, 12).map((track, index) => ({
          ...track,
          playlist_index: index,
        }));
        setTracks(preview);
        setPlaylists(data.playlists || []);
        onLikesContext(
          likes.playlist_uuid
            ? {
                playlist_kind: nextKind,
                playlist_uid: likes.uid ?? null,
                playlist_uuid: likes.playlist_uuid,
              }
            : null,
        );
        setStatus('ready');
      })
      .catch((reason: unknown) => {
        if (cancel) return;
        setError(reason instanceof Error ? reason.message : 'Ошибка загрузки');
        onLikesContext(null);
        setStatus('error');
      });
    return () => {
      cancel = true;
    };
  }, [onLikesContext]);

  const countText = status === 'error' ? '—' : status === 'loading' ? '…' : formatTrackCount(count);
  const slides: CatalogTrack[][] = [];
  for (let i = 0; i < tracks.length; i += 3) slides.push(tracks.slice(i, i + 3));

  return (
    <section className={active ? 'screen active' : 'screen'} id="screenHome">
      <div className="home-topbar">
        <button type="button" className="nav-btn" id="btnHomeQr" aria-label="Настройки" onClick={onQr}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.26.604.852.997 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
        <span className={connected ? 'status-dot online' : 'status-dot'} id="status" title={statusTitle} />
        <button type="button" className="nav-btn" id="btnHomeSearch" aria-label="Поиск" onClick={onSearch}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3-3" />
          </svg>
        </button>
      </div>
      <div className="home-scroll" id="homeScroll">
        <button
          type="button"
          className="likes-hero"
          id="likesHero"
          aria-label="Открыть «Мне нравится»"
          onClick={() => onOpenPlaylist(kind, title)}
        >
          <LikesArt url={cover} />
          <div className="likes-hero-body">
            <div className="likes-hero-title">
              <span id="likesHeroTitle">{title}</span>
              <span className="chev" aria-hidden="true">›</span>
            </div>
            <div className="likes-hero-count" id="likesTrackCount" hidden={status === 'ready' && !countText}>
              {countText}
            </div>
          </div>
        </button>
        <div className="likes-carousel" id="likesCarousel">
          {status === 'loading' ? <p className="list-meta">Загрузка…</p> : null}
          {status === 'error' ? <p className="list-meta">{error}</p> : null}
          {status === 'ready' && slides.length === 0 ? <p className="list-meta">Нет треков</p> : null}
          {status === 'ready'
            ? slides.map((slide, index) => (
                <div className="likes-slide" key={index}>
                  {slide.map((track) => (
                    <TrackRow
                      key={`${track.id}-${track.playlist_index}`}
                      track={track}
                      variant="likes"
                      onPlay={onPlay}
                      onMenu={onMenu}
                    />
                  ))}
                </div>
              ))
            : null}
        </div>
        <h2 className="home-section-title">Плейлисты</h2>
        <ul className="playlist-grid" id="playlistGrid">
          {status === 'error' ? <li className="list-meta">{error}</li> : null}
          {status === 'ready' && playlists.length === 0 ? <li className="list-meta">Нет плейлистов</li> : null}
          {status === 'ready'
            ? playlists.map((playlist) => (
                <li key={`${playlist.kind}-${playlist.playlist_uuid ?? ''}`}>
                  <button
                    type="button"
                    className="playlist-card"
                    onClick={() => onOpenPlaylist(playlist.kind, playlist.title)}
                  >
                    <CoverFrame url={playlist.cover_url} />
                    <div className="title">{playlist.title}</div>
                    {playlist.track_count ? <div className="meta">{playlist.track_count} треков</div> : null}
                  </button>
                </li>
              ))
            : null}
        </ul>
      </div>
    </section>
  );
}
